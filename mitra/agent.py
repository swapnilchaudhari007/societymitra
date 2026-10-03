"""SocietyMitra agent: Nano triages, Ultra reasons, Super drafts, Nano double-checks."""
from __future__ import annotations

from datetime import date, datetime

from .llm import TokenFactory, parse_json
from .rag import KnowledgeBase
from .store import dump, memory, remember, rows
from .tools import all_dues, dues_for_flat, web_search

LANGS = {"en": "English", "hi": "Hindi (Devanagari)", "mr": "Marathi (Devanagari)"}

TRIAGE_SYS = """You are the intake desk of a housing-society assistant in India.
Classify the user's message. Reply ONLY with JSON:
{"intent": "bylaw" | "dues" | "complaint" | "notice" | "remember" | "general",
 "flat": "<flat number like B-302 or empty>",
 "needs_web": true|false,   // true if it needs current law, govt resolutions, court rulings or anything outside a society rulebook
 "search_query": "<short web query if needs_web, else empty>",
 "urgency": "low" | "medium" | "high"}
bylaw = rights/rules/who-pays/is-it-allowed questions. dues = maintenance, arrears, interest, defaulters.
complaint = a member reporting a problem. notice = asks to draft a notice, circular, reminder or message.
remember = asks you to remember a society fact or decision."""

RULING_SYS = """You are SocietyMitra, an expert, neutral co-secretary for a co-operative housing society
in Maharashtra, India. Answer the question using ONLY the numbered sources given.
Rules:
- Cite every claim with [K#] (society knowledge) or [W#] (web). If sources don't cover it, say so plainly.
- Be practical: start with a one-line verdict, then "Why" (2-4 bullets), then "What the committee should do" (numbered steps).
- Never invent section numbers, amounts or dates that are not in the sources.
- Keep it under 220 words. Write in {lang}. End with: "Confidence: high/medium/low"."""

DRAFT_SYS = """You draft official communication for a co-operative housing society in India.
Tone: polite, firm, neutral, never shaming individuals in public notices.
Use the facts given; cite rule sources inline as (Ref: K#) where relevant.
Format: Title line, date, body, sign-off "Hon. Secretary, Managing Committee".
Write in {lang}. Also add, after a line '---WHATSAPP---', a short WhatsApp version (max 60 words)."""

CHECK_SYS = """You are a strict fact-checker. Given SOURCES and an ANSWER, list any claim in the ANSWER
not supported by the SOURCES. Reply ONLY with JSON: {"grounded": true|false, "unsupported": ["..."]}"""

COMPLAINT_SYS = """Classify a housing-society complaint. Reply ONLY with JSON:
{"category": "leakage" | "parking" | "noise" | "cleanliness" | "security" | "lift" | "water" | "pets" | "billing" | "other",
 "urgency": "low" | "medium" | "high", "summary": "<max 12 words>"}"""


class Mitra:
    def __init__(self, con, kb: KnowledgeBase, llm: TokenFactory | None = None):
        self.con, self.kb, self.llm = con, kb, llm or TokenFactory()

    # ---------- helpers ----------
    def _sources(self, query: str, needs_web: bool, web_query: str):
        hits = self.kb.search(query, k=4)
        k_src = [{"id": f"K{i+1}", "title": c.title, "source": c.source, "text": c.text}
                 for i, (_, c) in enumerate(hits)]
        w_src = []
        weak = not hits or hits[0][0] < 3.0
        if needs_web or weak:
            for i, r in enumerate(web_search(web_query or f"Maharashtra cooperative housing society {query}")):
                if r.get("url"):
                    w_src.append({"id": f"W{len(w_src)+1}", "title": r["title"], "url": r["url"], "text": r["content"]})
        return k_src, w_src

    @staticmethod
    def _fmt_sources(k_src, w_src) -> str:
        out = [f"[{s['id']}] {s['title']} ({s['source']}): {s['text']}" for s in k_src]
        out += [f"[{s['id']}] {s['title']} <{s['url']}>: {s['text']}" for s in w_src]
        return "\n\n".join(out) or "(no sources found)"

    def _society_context(self) -> str:
        return "Society memory:\n- " + "\n- ".join(memory(self.con)) + f"\nToday: {date.today().isoformat()}"

    # ---------- main entry ----------
    def handle(self, message: str, language: str = "en") -> dict:
        lang = LANGS.get(language, "English")
        traces = []
        tri = self.llm.chat("nano", [{"role": "system", "content": TRIAGE_SYS},
                                     {"role": "user", "content": message}],
                            "triage", temperature=0, max_tokens=200, json_mode=True)
        traces.append(tri.trace)
        t = parse_json(tri.text, {"intent": "general", "needs_web": False, "flat": "", "search_query": "", "urgency": "low"})
        intent = t.get("intent", "general")
        handler = {"bylaw": self._ruling, "general": self._ruling, "dues": self._dues,
                   "complaint": self._complaint, "notice": self._notice,
                   "remember": self._remember}.get(intent, self._ruling)
        result = handler(message, t, lang, traces)
        result.update({"intent": intent, "triage": t,
                       "trace": [tr.__dict__ for tr in traces],
                       "live": self.llm.live})
        return result

    def _ruling(self, message, t, lang, traces):
        k_src, w_src = self._sources(message, bool(t.get("needs_web")), t.get("search_query", ""))
        sources = self._fmt_sources(k_src, w_src)
        res = self.llm.chat("ultra", [
            {"role": "system", "content": RULING_SYS.replace("{lang}", lang)},
            {"role": "user", "content": f"{self._society_context()}\n\nSOURCES:\n{sources}\n\nQUESTION: {message}"}],
            "ruling", temperature=0.2, max_tokens=1500)
        traces.append(res.trace)
        chk = self.llm.chat("nano", [
            {"role": "system", "content": CHECK_SYS},
            {"role": "user", "content": f"SOURCES:\n{sources}\n\nANSWER:\n{res.text}"}],
            "grounding-check", temperature=0, max_tokens=300, json_mode=True)
        traces.append(chk.trace)
        check = parse_json(chk.text, {"grounded": True, "unsupported": []})
        return {"answer": res.text, "sources": k_src + w_src, "check": check}

    def _dues(self, message, t, lang, traces):
        flat = (t.get("flat") or "").upper().replace(" ", "")
        data = dues_for_flat(self.con, flat) if flat else {
            "defaulters": [d for d in all_dues(self.con) if d["months_unpaid"]]}
        k_src, _ = self._sources("interest late payment defaulters recovery", False, "")
        res = self.llm.chat("super", [
            {"role": "system", "content": RULING_SYS.replace("{lang}", lang) +
             "\nThe LEDGER numbers are computed by the society's software and are exact; quote them, never recompute."},
            {"role": "user", "content": f"{self._society_context()}\n\nLEDGER:\n{dump(data)}\n\nSOURCES:\n"
                                        f"{self._fmt_sources(k_src, [])}\n\nQUESTION: {message}"}],
            "dues-explain", temperature=0.2, max_tokens=900)
        traces.append(res.trace)
        return {"answer": res.text, "sources": k_src, "ledger": data}

    def _complaint(self, message, t, lang, traces):
        c = self.llm.chat("nano", [{"role": "system", "content": COMPLAINT_SYS},
                                   {"role": "user", "content": message}],
                          "complaint-classify", temperature=0, max_tokens=150, json_mode=True)
        traces.append(c.trace)
        meta = parse_json(c.text, {"category": "other", "urgency": "medium", "summary": message[:60]})
        k_src, w_src = self._sources(f"{meta.get('category')} {message}", bool(t.get("needs_web")), t.get("search_query", ""))
        res = self.llm.chat("ultra", [
            {"role": "system", "content": RULING_SYS.replace("{lang}", lang) +
             "\nThis is a member complaint. Give: who is responsible, a fair resolution, and a written reply to the member."},
            {"role": "user", "content": f"{self._society_context()}\n\nSOURCES:\n{self._fmt_sources(k_src, w_src)}\n\nCOMPLAINT: {message}"}],
            "complaint-resolution", temperature=0.2, max_tokens=1500)
        traces.append(res.trace)
        cur = self.con.execute(
            "INSERT INTO complaints(flat,text,category,urgency,status,reply,created) VALUES(?,?,?,?,?,?,?)",
            (t.get("flat", ""), message, meta.get("category"), meta.get("urgency"), "open", res.text,
             datetime.now().isoformat(timespec="minutes")))
        self.con.commit()
        return {"answer": res.text, "sources": k_src + w_src, "complaint": {"id": cur.lastrowid, **meta}}

    def _notice(self, message, t, lang, traces):
        k_src, _ = self._sources(message, False, "")
        extra = ""
        if any(w in message.lower() for w in ("defaulter", "dues", "arrear", "maintenance")):
            extra = "\nLEDGER (exact):\n" + dump([d for d in all_dues(self.con) if d["months_unpaid"]])
        res = self.llm.chat("super", [
            {"role": "system", "content": DRAFT_SYS.replace("{lang}", lang)},
            {"role": "user", "content": f"{self._society_context()}{extra}\n\nSOURCES:\n"
                                        f"{self._fmt_sources(k_src, [])}\n\nREQUEST: {message}"}],
            "draft-notice", temperature=0.4, max_tokens=1400)
        traces.append(res.trace)
        body, _, wa = res.text.partition("---WHATSAPP---")
        title = body.strip().split("\n")[0].strip("# *")[:120]
        self.con.execute("INSERT INTO notices(title,body,language,created) VALUES(?,?,?,?)",
                         (title, body.strip(), lang, datetime.now().isoformat(timespec="minutes")))
        self.con.commit()
        return {"answer": body.strip(), "whatsapp": wa.strip(), "sources": k_src}

    def _remember(self, message, t, lang, traces):
        fact = message.split(":", 1)[-1].strip() if ":" in message else message
        remember(self.con, fact)
        return {"answer": f"Saved to society memory: \"{fact}\". I'll use it in future answers.",
                "sources": [], "memory": memory(self.con)}

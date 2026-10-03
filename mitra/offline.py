"""Offline fallback used ONLY when NEBIUS_API_KEY is missing (tests, CI, first-run).
Every offline answer is labelled so it can never be mistaken for a Nemotron response."""
from __future__ import annotations

import json
import re

BANNER = "[Offline mode - add NEBIUS_API_KEY to get Nemotron answers]\n\n"


def _triage(text: str) -> str:
    t = text.lower()
    flat = re.search(r"\b([a-z])\s*-?\s*(\d{3})\b", t)
    intent = "bylaw"
    if t.startswith("remember"):
        intent = "remember"
    elif any(w in t for w in ("draft", "notice", "circular", "write a", "message to")):
        intent = "notice"
    elif any(w in t for w in ("dues", "arrear", "outstanding", "defaulter", "how much does")):
        intent = "dues"
    elif any(w in t for w in ("leak", "complain", "noise", "broken", "not working", "dirty")):
        intent = "complaint"
    return json.dumps({"intent": intent,
                       "flat": f"{flat.group(1).upper()}-{flat.group(2)}" if flat else "",
                       "needs_web": False, "search_query": "", "urgency": "medium"})


def offline_reply(step: str, messages: list[dict]) -> str:
    user = messages[-1]["content"]
    if step == "triage":
        return _triage(user)
    if step == "grounding-check":
        return json.dumps({"grounded": True, "unsupported": []})
    if step == "complaint-classify":
        cat = "leakage" if "leak" in user.lower() else "other"
        return json.dumps({"category": cat, "urgency": "medium", "summary": user[:60]})
    cites = re.findall(r"\[(K\d+)\] ([^(]+)", user)
    refs = ", ".join(f"{k} {t.strip()}" for k, t in cites[:3]) or "no matching sources"
    if step == "draft-notice":
        return (BANNER + "NOTICE\n\nDear Members,\nThis is a draft notice generated offline. "
                f"Relevant rules: {refs}.\n\nHon. Secretary, Managing Committee\n---WHATSAPP---\n"
                "Dear members, please see the notice on the board. - Secretary")
    return BANNER + f"Most relevant society rules found: {refs}."

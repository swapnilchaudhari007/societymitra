"""Deterministic tools the agent calls. Money maths never goes through an LLM."""
from __future__ import annotations

import os
from datetime import date

import httpx

from .store import rows

TAVILY_URL = "https://api.tavily.com/search"


def dues_for_flat(con, flat: str, rate_pa: float = 18.0, today: date | None = None) -> dict:
    """Outstanding dues with simple interest (capped at 21% p.a. by the model bye-laws)."""
    today = today or date.today()
    rate = min(rate_pa, 21.0)
    items, principal, interest = [], 0.0, 0.0
    for d in rows(con, "SELECT * FROM dues WHERE flat=? AND paid_on IS NULL ORDER BY period", flat):
        days = max((today - date.fromisoformat(d["due_date"])).days, 0)
        i = round(d["amount"] * rate / 100 * days / 365, 2)
        items.append({"period": d["period"], "amount": d["amount"], "days_late": days, "interest": i})
        principal += d["amount"]
        interest += i
    return {"flat": flat, "rate_pa": rate, "months_unpaid": len(items),
            "principal": round(principal, 2), "interest": round(interest, 2),
            "total": round(principal + interest, 2), "items": items,
            "defaulter": len(items) >= 3}


def all_dues(con, rate_pa: float = 18.0) -> list[dict]:
    flats = [r["flat"] for r in rows(con, "SELECT flat FROM members ORDER BY flat")]
    out = []
    for f in flats:
        d = dues_for_flat(con, f, rate_pa)
        d["name"] = rows(con, "SELECT name FROM members WHERE flat=?", f)[0]["name"]
        out.append(d)
    return out


def web_search(query: str, max_results: int = 4) -> list[dict]:
    """Live legal/government lookup through Tavily. Returns [] if no key configured."""
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        return []
    try:
        r = httpx.post(TAVILY_URL, timeout=30,
                       headers={"Authorization": f"Bearer {key}"},
                       json={"query": query, "search_depth": "advanced", "max_results": max_results,
                             "include_answer": False, "country": "india"})
        if r.status_code == 400:  # older API versions don't accept 'country'
            r = httpx.post(TAVILY_URL, timeout=30, headers={"Authorization": f"Bearer {key}"},
                           json={"query": query, "search_depth": "advanced", "max_results": max_results})
        r.raise_for_status()
        return [{"title": x.get("title", ""), "url": x.get("url", ""),
                 "content": (x.get("content") or "")[:900]} for x in r.json().get("results", [])]
    except Exception as e:  # never break the answer because search failed
        return [{"title": "search unavailable", "url": "", "content": str(e)[:200]}]

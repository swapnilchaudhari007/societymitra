import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.pop("NEBIUS_API_KEY", None)
os.environ["MITRA_DB"] = ":memory:"

from mitra.agent import Mitra  # noqa: E402
from mitra.llm import TokenFactory, strip_reasoning  # noqa: E402
from mitra.rag import KnowledgeBase  # noqa: E402
from mitra.store import connect, seed  # noqa: E402
from mitra.tools import dues_for_flat  # noqa: E402


def setup():
    con = connect()
    seed(con, today=date(2026, 10, 3))
    kb = KnowledgeBase()
    kb.load_dir(ROOT / "knowledge")
    return con, kb


def test_retrieval_finds_leakage_rule():
    _, kb = setup()
    top = kb.search("water leaking from upper flat bathroom who pays repair")[0][1]
    assert "leakage" in top.title.lower()


def test_retrieval_finds_non_occupancy():
    _, kb = setup()
    titles = [c.title for _, c in kb.search("tenant non occupancy charges percent")]
    assert any("Non-occupancy" in t for t in titles)


def test_interest_is_simple_and_capped():
    con, _ = setup()
    d = dues_for_flat(con, "B-302", rate_pa=30, today=date(2026, 10, 3))
    assert d["rate_pa"] == 21.0
    assert d["months_unpaid"] == 5 and d["defaulter"]
    assert d["principal"] == 5 * 2850


def test_clear_flat_has_no_dues():
    con, _ = setup()
    assert dues_for_flat(con, "B-101")["total"] == 0


def test_strip_think():
    assert strip_reasoning("<think>hmm</think> Answer") == "Answer"


def test_agent_routes_offline():
    con, kb = setup()
    m = Mitra(con, kb, TokenFactory(api_key=None))
    r = m.handle("Water is leaking from B-301 bathroom into B-201. Who pays?")
    assert r["intent"] == "complaint" and r["complaint"]["category"] == "leakage"
    assert r["trace"][0]["tier"] == "nano"
    r = m.handle("Draft a reminder notice for pending maintenance")
    assert r["intent"] == "notice" and r["whatsapp"]
    r = m.handle("Remember: AGM approved lift replacement")
    assert "lift" in r["memory"][-1]

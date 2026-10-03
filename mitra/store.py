"""SQLite store: members, dues ledger, complaints, notices and Mitra's society memory."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import date, datetime

DB_PATH = os.getenv("MITRA_DB", "societymitra.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS members(
  flat TEXT PRIMARY KEY, name TEXT, phone TEXT, area_sqft INTEGER, occupancy TEXT);
CREATE TABLE IF NOT EXISTS dues(
  id INTEGER PRIMARY KEY AUTOINCREMENT, flat TEXT, period TEXT, amount REAL,
  due_date TEXT, paid_on TEXT);
CREATE TABLE IF NOT EXISTS complaints(
  id INTEGER PRIMARY KEY AUTOINCREMENT, flat TEXT, text TEXT, category TEXT,
  urgency TEXT, status TEXT, reply TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS notices(
  id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, body TEXT, language TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS memory(
  id INTEGER PRIMARY KEY AUTOINCREMENT, fact TEXT, created TEXT);
"""

SEED_MEMBERS = [
    ("B-101", "A. Patil", "98xxxxxx01", 650, "owner"),
    ("B-102", "R. Shaikh", "98xxxxxx02", 650, "owner"),
    ("B-201", "S. Iyer", "98xxxxxx03", 720, "tenant"),
    ("B-202", "M. Deshmukh", "98xxxxxx04", 720, "owner"),
    ("B-301", "K. Jadhav", "98xxxxxx05", 650, "owner"),
    ("B-302", "P. Fernandes", "98xxxxxx06", 650, "locked"),
    ("B-401", "N. Gupta", "98xxxxxx07", 720, "owner"),
    ("B-402", "V. More", "98xxxxxx08", 720, "tenant"),
]


def connect():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def seed(con, today: date | None = None):
    """Demo data for a fictional 8-flat wing so the app is useful on first launch."""
    if con.execute("SELECT COUNT(*) FROM members").fetchone()[0]:
        return
    today = today or date.today()
    con.executemany("INSERT INTO members VALUES(?,?,?,?,?)", SEED_MEMBERS)
    months = []
    y, m = today.year, today.month
    for _ in range(6):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        months.append((y, m))
    months.reverse()
    unpaid = {"B-302": 5, "B-402": 3, "B-201": 1}  # months unpaid at the end
    for flat, *_ in SEED_MEMBERS:
        for i, (yy, mm) in enumerate(months):
            due = date(yy, mm, 10).isoformat()
            paid = None if i >= len(months) - unpaid.get(flat, 0) else date(yy, mm, 8).isoformat()
            con.execute("INSERT INTO dues(flat,period,amount,due_date,paid_on) VALUES(?,?,?,?,?)",
                        (flat, f"{yy}-{mm:02d}", 2850.0, due, paid))
    con.execute("INSERT INTO memory(fact,created) VALUES(?,?)",
                ("Society: fictional demo wing 'Sunrise B Wing CHS', Thane, Maharashtra. "
                 "Interest on arrears approved by AGM at 18% p.a. simple.", datetime.now().isoformat()))
    con.commit()


def rows(con, sql, *args):
    return [dict(r) for r in con.execute(sql, args).fetchall()]


def remember(con, fact: str):
    con.execute("INSERT INTO memory(fact,created) VALUES(?,?)", (fact, datetime.now().isoformat()))
    con.commit()


def memory(con) -> list[str]:
    return [r["fact"] for r in rows(con, "SELECT fact FROM memory ORDER BY id")]


def dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1)

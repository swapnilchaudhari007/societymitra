"""SocietyMitra web server.  Run:  uvicorn app:app --reload"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from mitra.agent import Mitra
from mitra.llm import TokenFactory
from mitra.rag import KnowledgeBase
from mitra.store import connect, memory, rows, seed
from mitra.tools import all_dues

ROOT = Path(__file__).parent
con = connect()
seed(con)
kb = KnowledgeBase()
kb.load_dir(ROOT / "knowledge")
llm = TokenFactory()
llm.discover()
mitra = Mitra(con, kb, llm)

app = FastAPI(title="SocietyMitra")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


class Ask(BaseModel):
    message: str
    language: str = "en"


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/status")
def status():
    return {"live": llm.live, "models": llm.models, "tavily": bool(os.getenv("TAVILY_API_KEY")),
            "knowledge_sections": len(kb.chunks)}


@app.post("/api/ask")
def ask(q: Ask):
    if not q.message.strip():
        raise HTTPException(400, "Empty message")
    try:
        return mitra.handle(q.message.strip()[:4000], q.language)
    except Exception as e:  # surface model/API errors to the UI instead of a blank 500
        raise HTTPException(502, f"Model call failed: {e}")


@app.get("/api/dues")
def dues():
    return all_dues(con)


@app.get("/api/complaints")
def complaints():
    return rows(con, "SELECT * FROM complaints ORDER BY id DESC")


@app.post("/api/complaints/{cid}/resolve")
def resolve(cid: int):
    con.execute("UPDATE complaints SET status='resolved' WHERE id=?", (cid,))
    con.commit()
    return {"ok": True}


@app.get("/api/notices")
def notices():
    return rows(con, "SELECT * FROM notices ORDER BY id DESC")


@app.get("/api/memory")
def get_memory():
    return memory(con)


@app.post("/api/bylaws")
async def upload_bylaws(file: UploadFile = File(...)):
    raw = await file.read()
    if len(raw) > 2_000_000:
        raise HTTPException(413, "Keep uploads under 2 MB of text")
    text = raw.decode("utf-8", errors="ignore")
    n = kb.add_markdown(file.filename or "uploaded bye-laws", text)
    return {"added_sections": n, "total": len(kb.chunks)}

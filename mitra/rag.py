"""Tiny dependency-free BM25 retriever over society knowledge (bye-laws, circulars).

Sections are split on markdown headings (or paragraphs for uploaded plain text), so
every answer can cite the exact section it relied on.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

STOP = set("""a an the of to in on for and or is are be by with as at from that this it its
not can may must any all if when who which their they them his her he she we our you your
per up into than then""".split())


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOP and len(t) > 1]


@dataclass
class Chunk:
    source: str
    title: str
    text: str


class KnowledgeBase:
    def __init__(self):
        self.chunks: list[Chunk] = []
        self._tf: list[Counter] = []
        self._df: Counter = Counter()
        self._avgdl = 0.0

    def add_markdown(self, source: str, text: str):
        parts = re.split(r"^##\s+", text, flags=re.M)
        added = 0
        for part in parts[1:] if len(parts) > 1 else []:
            title, _, body = part.partition("\n")
            body = body.strip()
            if body:
                self._add(Chunk(source, title.strip(), body))
                added += 1
        if not added:  # plain text upload: chunk by paragraphs
            for i, para in enumerate(p for p in re.split(r"\n\s*\n", text) if p.strip()):
                first = para.strip().split("\n")[0][:60]
                self._add(Chunk(source, f"{first}", para.strip()))
                added += 1
        self._reindex()
        return added

    def load_dir(self, folder: str | Path):
        for p in sorted(Path(folder).glob("*.md")):
            self.add_markdown(p.stem.replace("_", " "), p.read_text(encoding="utf-8"))

    def _add(self, c: Chunk):
        self.chunks.append(c)

    def _reindex(self):
        self._tf = [Counter(tokenize(c.title + " " + c.text)) for c in self.chunks]
        self._df = Counter()
        for tf in self._tf:
            self._df.update(tf.keys())
        self._avgdl = sum(sum(tf.values()) for tf in self._tf) / max(len(self._tf), 1)

    def search(self, query: str, k: int = 4, k1: float = 1.5, b: float = 0.75) -> list[tuple[float, Chunk]]:
        q = tokenize(query)
        n = len(self.chunks)
        scored = []
        for tf, chunk in zip(self._tf, self.chunks):
            dl = sum(tf.values())
            s = 0.0
            for term in q:
                if term not in tf:
                    continue
                idf = math.log(1 + (n - self._df[term] + 0.5) / (self._df[term] + 0.5))
                s += idf * tf[term] * (k1 + 1) / (tf[term] + k1 * (1 - b + b * dl / self._avgdl))
            if s > 0:
                scored.append((s, chunk))
        scored.sort(key=lambda x: -x[0])
        return scored[:k]

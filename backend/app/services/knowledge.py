"""Tiny retrieval layer over the fashion knowledge base (BM25-style keyword scoring).

Swap for an embedding index (e.g. Gemini embeddings + FAISS) once the KB grows.
"""

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

KB_PATH = Path(__file__).resolve().parent.parent / "data" / "fashion_kb.json"
_WORD = re.compile(r"[a-z0-9]+")
_STOP = {
    "a", "an", "the", "to", "for", "of", "and", "or", "in", "on", "at", "is", "i", "me", "my",
    "what", "should", "wear", "with", "it", "be", "do", "can", "you", "how", "some", "this",
}


@dataclass(frozen=True)
class Doc:
    id: str
    title: str
    text: str
    tokens: tuple[str, ...]


def _tokenize(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOP]


@lru_cache
def _index() -> tuple[list[Doc], dict[str, float], float]:
    raw = json.loads(KB_PATH.read_text())
    docs = []
    for d in raw:
        # Tags are weighted x3: they're curated signals of what the entry is about.
        tokens = _tokenize(d["title"] + " " + d["text"]) + _tokenize(" ".join(d["tags"])) * 3
        docs.append(Doc(d["id"], d["title"], d["text"], tuple(tokens)))
    df = Counter(t for d in docs for t in set(d.tokens))
    n = len(docs)
    idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
    avg_len = sum(len(d.tokens) for d in docs) / n
    return docs, idf, avg_len


def search(query: str, k: int = 3) -> list[Doc]:
    docs, idf, avg_len = _index()
    q = _tokenize(query)
    k1, b = 1.5, 0.75
    scored = []
    for d in docs:
        tf = Counter(d.tokens)
        score = 0.0
        for t in q:
            if t in tf:
                f = tf[t]
                score += idf[t] * f * (k1 + 1) / (f + k1 * (1 - b + b * len(d.tokens) / avg_len))
        if score > 0:
            scored.append((score, d))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in scored[:k]]

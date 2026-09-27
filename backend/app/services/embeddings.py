"""768-dimensional embeddings for semantic catalog search.

Providers:
  replicate  CLIP ViT-L/14 (text and images share one space), as in the specification
  gemini     gemini-embedding-001 truncated to 768 dims (text only)
  hash       deterministic feature hashing, no network: keyword-level similarity for offline dev

Garments store which model produced their vector; `scripts/seed_catalog.py --reembed` rebuilds
vectors after switching providers, since vectors from different models aren't comparable.
"""

import asyncio
import hashlib
import math
import re

from app.core.config import get_settings
from app.core.spend import record_paid_call

DIM = 768
_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"a", "an", "the", "and", "or", "with", "for", "of", "in", "on", "to", "me", "my", "i", "what", "wear", "should"}


def provider() -> str:
    s = get_settings()
    if s.embedding_provider != "auto":
        return s.embedding_provider
    if s.use_mock:
        return "hash"
    if s.replicate_api_token:
        return "replicate"
    if s.gemini_api_key:
        return "gemini"
    return "hash"


def model_name() -> str:
    return {
        "replicate": "clip-vit-l-14",
        "gemini": get_settings().gemini_embedding_model,
        "hash": "hash-v1",
    }[provider()]


def hash_embed(text: str) -> list[float]:
    vec = [0.0] * DIM
    words = [w for w in _WORD.findall(text.lower()) if w not in _STOP]
    grams = words + [f"{a}_{b}" for a, b in zip(words, words[1:], strict=False)]
    for g in grams:
        h = hashlib.blake2b(g.encode(), digest_size=8).digest()
        idx = int.from_bytes(h[:4], "big") % DIM
        sign = 1.0 if h[4] & 1 else -1.0
        vec[idx] += sign * (1.5 if "_" in g else 1.0)
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    p = provider()
    if p == "hash":
        return [hash_embed(t) for t in texts]
    if p == "gemini":
        return await asyncio.to_thread(_gemini_embed, texts)
    return await _replicate_clip(texts)


async def embed_text(text: str) -> list[float]:
    return (await embed_texts([text]))[0]


def _gemini_embed(texts: list[str]) -> list[list[float]]:
    from google.genai import types

    from app.services import gemini

    record_paid_call("gemini")
    resp = gemini.client().models.embed_content(
        model=get_settings().gemini_embedding_model,
        contents=texts,
        config=types.EmbedContentConfig(output_dimensionality=DIM),
    )
    out = []
    for e in resp.embeddings:
        norm = math.sqrt(sum(v * v for v in e.values)) or 1.0
        out.append([v / norm for v in e.values])
    return out


async def _replicate_clip(texts: list[str]) -> list[list[float]]:
    from app.services import replicate_client as rep

    record_paid_call("replicate")
    output = await rep.run(get_settings().replicate_clip_model, {"inputs": "\n".join(texts)})
    vectors = [item["embedding"] for item in output]
    if any(len(v) != DIM for v in vectors):
        raise ValueError("CLIP model returned an unexpected embedding size")
    return vectors

"""Adapter: RAG strategy (local embeddings + FAISS).

The FAISS index is built once per (corpus, params) pair and cached on ctx.
"""
from __future__ import annotations

from ..registry import strategy
from src.strategies_rag import build_index, rag_prompt


@strategy("rag_embedding")
async def run(ctx, question, corpus, *, k: int = 6, **_):
    cache = ctx.setdefault("_rag_index", {})
    key = (id(corpus), k)
    if key not in cache:
        cache[key] = build_index(corpus.as_legacy_list())
    idx = cache[key]
    retrieved = idx.top_k(question.input, k=k)
    return rag_prompt(question.input, retrieved)

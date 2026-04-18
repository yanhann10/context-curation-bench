"""Stage 2 — RAG strategy with FAISS.

Chunk docs, embed with OpenAI text-embedding-3-small, retrieve top-k via
FAISS flat inner-product (embeddings are L2-normalized so IP == cosine).
"""
from __future__ import annotations
import hashlib
from dataclasses import dataclass

import faiss
import numpy as np
from openai import AsyncOpenAI


EMBED_MODEL = "text-embedding-3-small"
CHUNK_CHARS = 1200
OVERLAP_CHARS = 200


@dataclass
class Chunk:
    doc_id: str
    chunk_id: str
    text: str
    meta: dict


def chunk_doc(doc: dict, chunk_chars: int = CHUNK_CHARS, overlap: int = OVERLAP_CHARS) -> list[Chunk]:
    body = doc["content"]
    if len(body) <= chunk_chars:
        h = hashlib.md5(body.encode()).hexdigest()[:6]
        return [Chunk(doc["id"], f"{doc['id']}#{h}", body, doc["metadata"])]
    chunks: list[Chunk] = []
    i = 0
    while i < len(body):
        piece = body[i : i + chunk_chars]
        h = hashlib.md5(piece.encode()).hexdigest()[:6]
        chunks.append(Chunk(doc["id"], f"{doc['id']}#{h}", piece, doc["metadata"]))
        i += chunk_chars - overlap
    return chunks


async def embed_texts(client: AsyncOpenAI, texts: list[str], model: str = EMBED_MODEL) -> np.ndarray:
    vecs: list[list[float]] = []
    for i in range(0, len(texts), 96):
        batch = texts[i : i + 96]
        resp = await client.embeddings.create(model=model, input=batch)
        vecs.extend([d.embedding for d in resp.data])
    arr = np.asarray(vecs, dtype=np.float32)
    faiss.normalize_L2(arr)  # in-place L2 normalization so IP == cosine
    return arr


class RagIndex:
    def __init__(self, chunks: list[Chunk], vectors: np.ndarray):
        assert len(chunks) == vectors.shape[0]
        self.chunks = chunks
        self.dim = vectors.shape[1]
        self.index = faiss.IndexFlatIP(self.dim)
        self.index.add(vectors)

    async def top_k(self, client: AsyncOpenAI, query: str, k: int = 6) -> list[Chunk]:
        qv = await embed_texts(client, [query])
        _, idx = self.index.search(qv, k)
        return [self.chunks[i] for i in idx[0] if 0 <= i < len(self.chunks)]


async def build_index(client: AsyncOpenAI, docs: list[dict]) -> RagIndex:
    all_chunks: list[Chunk] = []
    for d in docs:
        all_chunks.extend(chunk_doc(d))
    vecs = await embed_texts(client, [c.text for c in all_chunks])
    return RagIndex(all_chunks, vecs)


def render_chunks(chunks: list[Chunk]) -> str:
    parts = []
    for c in chunks:
        title = c.meta.get("title", c.doc_id)
        src = c.meta.get("source", "")
        ts = c.meta.get("timestamp", "")
        header = f"--- {title} [{src}{(' @ ' + ts) if ts else ''}] ---"
        parts.append(f"{header}\n{c.text}")
    return "\n\n".join(parts)


def rag_prompt(question: str, retrieved: list[Chunk]) -> str:
    return (
        "You are a helpful New Hire Onboarding assistant. "
        "Answer using ONLY the sources below. If sources disagree, prefer the most recent. "
        "Cite source titles in square brackets.\n\n"
        f"=== RETRIEVED SOURCES ({len(retrieved)}) ===\n"
        f"{render_chunks(retrieved)}\n\n"
        f"=== QUESTION ===\n{question}"
    )


async def rag_build_prompt_fn(client: AsyncOpenAI, docs: list[dict], k: int = 6):
    """Return an async prompt_fn(question, docs) compatible with run_strategy_async."""
    index = await build_index(client, docs)

    async def prompt_fn(q: str, _docs) -> str:
        retrieved = await index.top_k(client, q, k=k)
        return rag_prompt(q, retrieved)

    return prompt_fn

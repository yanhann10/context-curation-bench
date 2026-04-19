"""Stage 2 — RAG strategy. Local embeddings (sentence-transformers) + FAISS."""
from __future__ import annotations
import hashlib
from dataclasses import dataclass

import faiss
import numpy as np

from .embeddings import embed


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


class RagIndex:
    def __init__(self, chunks: list[Chunk], vectors: np.ndarray):
        assert len(chunks) == vectors.shape[0]
        self.chunks = chunks
        self.dim = vectors.shape[1]
        self.index = faiss.IndexFlatIP(self.dim)
        self.index.add(vectors)

    def top_k(self, query: str, k: int = 6) -> list[Chunk]:
        qv = embed([query])
        _, idx = self.index.search(qv, k)
        return [self.chunks[i] for i in idx[0] if 0 <= i < len(self.chunks)]


def build_index(docs: list[dict]) -> RagIndex:
    all_chunks: list[Chunk] = []
    for d in docs:
        all_chunks.extend(chunk_doc(d))
    vecs = embed([c.text for c in all_chunks])
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
        "Answer using ONLY the sources below. If sources disagree, prefer the most recent. "
        "Cite source titles in square brackets. Do NOT refuse based on domain assumptions.\n\n"
        f"=== RETRIEVED SOURCES ({len(retrieved)}) ===\n"
        f"{render_chunks(retrieved)}\n\n"
        f"=== QUESTION ===\n{question}"
    )


async def rag_build_prompt_fn(client, docs: list[dict], k: int = 6):
    """Build FAISS index once; return async prompt_fn (client unused — local embed).

    Signature kept client-first for parity with hierarchical_build_prompt_fn.
    """
    index = build_index(docs)

    async def prompt_fn(q: str, _docs) -> str:
        retrieved = index.top_k(q, k=k)
        return rag_prompt(q, retrieved)

    return prompt_fn

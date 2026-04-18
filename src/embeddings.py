"""Local embeddings via sentence-transformers.

Claude doesn't expose an embedding endpoint, so we use BGE-small-en-v1.5
(BAAI, ~133 MB, CPU-friendly). Returns L2-normalized float32 so FAISS
IndexFlatIP gives cosine similarity.
"""
from __future__ import annotations
import threading

import numpy as np


_MODEL = None
_MODEL_LOCK = threading.Lock()
DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


def get_model(name: str = DEFAULT_MODEL):
    global _MODEL
    with _MODEL_LOCK:
        if _MODEL is None:
            from sentence_transformers import SentenceTransformer
            _MODEL = SentenceTransformer(name)
        return _MODEL


def embed(texts: list[str], batch_size: int = 64) -> np.ndarray:
    """Embed + L2-normalize. Returns (n, d) float32."""
    m = get_model()
    vecs = m.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    ).astype(np.float32)
    return vecs

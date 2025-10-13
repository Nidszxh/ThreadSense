"""Local sentence-transformers embeddings (all-MiniLM-L6-v2), lazy-loaded per process."""

from __future__ import annotations

import logging

import torch
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

_model: SentenceTransformer | None = None


def get_device() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("Loading embedding model %s on %s", MODEL_NAME, get_device())
        _model = SentenceTransformer(MODEL_NAME, device=get_device())
    return _model


def embed_texts(texts: list[str]) -> list[list[float] | None]:
    """Embed non-empty texts; empty strings map to None."""
    texts = [t or "" for t in texts]
    results: list[list[float] | None] = [None] * len(texts)
    to_embed = [(i, t) for i, t in enumerate(texts) if t.strip()]
    if not to_embed:
        return results
    model = get_model()
    embeddings = model.encode(
        [t for _, t in to_embed],
        batch_size=64,
        convert_to_numpy=True,
        show_progress_bar=False,
        device=get_device(),
    )
    for (i, _), emb in zip(to_embed, embeddings):
        results[i] = emb.tolist()
    return results


def reset_model() -> None:
    global _model
    _model = None

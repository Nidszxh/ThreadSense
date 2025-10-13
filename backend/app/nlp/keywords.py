"""KeyBERT keyword extraction, mirroring the research pipeline's knobs.

Reference: `src/thread_keyword_extraction.py` (KeyBERTProcessor).
"""

from __future__ import annotations

import logging

from keybert import KeyBERT

from app.nlp.embeddings import get_model

logger = logging.getLogger(__name__)

NGRAM_RANGE = (1, 2)
TOP_N = 10
STOP_WORDS = "english"

_extractor: KeyBERT | None = None


def get_extractor() -> KeyBERT:
    global _extractor
    if _extractor is None:
        logger.info("Initializing KeyBERT extractor")
        _extractor = KeyBERT(model=get_model())
    return _extractor


def extract_keywords(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    keywords = get_extractor().extract_keywords(
        text,
        keyphrase_ngram_range=NGRAM_RANGE,
        stop_words=STOP_WORDS,
        top_n=TOP_N,
    )
    return [kw for kw, _ in keywords]

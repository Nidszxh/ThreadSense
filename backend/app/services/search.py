"""Keyword (Postgres FTS) + semantic (pgvector) search over stored threads.

- Keyword: `to_tsvector` GIN indexes on `comments.body` and
  `summaries.content` (added in migration 0002), ranked by `ts_rank`.
- Semantic: nearest `comment_features.embedding` (all-MiniLM-L6-v2) by cosine
  distance (`<=>`), so it needs at least one processed thread.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pgvector.sqlalchemy import Vector
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.nlp.embeddings import embed_texts

logger = logging.getLogger(__name__)

COMMENT_SELECT = """
    c.id, c.thread_id, t.title AS thread_title, c.author, c.body
"""


@dataclass
class CommentHit:
    id: int
    thread_id: int
    thread_title: str
    author: str | None
    body: str
    score: float
    distance: float | None = None


@dataclass
class SummaryHit:
    id: int
    thread_id: int
    thread_title: str
    kind: str
    content: dict
    score: float


def _query_doc(query: str) -> str:
    return " ".join(query.split())


def keyword_search_comments(
    db: Session, query: str, limit: int = 20
) -> list[CommentHit]:
    q = _query_doc(query)
    if not q:
        return []
    sql = text(
        f"""
        SELECT {COMMENT_SELECT},
               ts_rank(to_tsvector('english', c.body), plainto_tsquery('english', :q)) AS rank
        FROM comments c
        JOIN threads t ON t.id = c.thread_id
        WHERE to_tsvector('english', c.body) @@ plainto_tsquery('english', :q)
        ORDER BY rank DESC, c.score DESC
        LIMIT :limit
        """
    )
    rows = db.execute(sql, {"q": q, "limit": limit}).mappings().all()
    return [
        CommentHit(
            id=r["id"],
            thread_id=r["thread_id"],
            thread_title=r["thread_title"],
            author=r["author"],
            body=r["body"],
            score=float(r["rank"]),
        )
        for r in rows
    ]


def keyword_search_summaries(
    db: Session, query: str, limit: int = 20
) -> list[SummaryHit]:
    q = _query_doc(query)
    if not q:
        return []
    sql = text(
        """
        SELECT s.id, s.thread_id, t.title AS thread_title, s.kind, s.content,
               ts_rank(to_tsvector('english', s.content::text), plainto_tsquery('english', :q)) AS rank
        FROM summaries s
        JOIN threads t ON t.id = s.thread_id
        WHERE to_tsvector('english', s.content::text) @@ plainto_tsquery('english', :q)
        ORDER BY rank DESC, s.created_at DESC
        LIMIT :limit
        """
    )
    rows = db.execute(sql, {"q": q, "limit": limit}).mappings().all()
    return [
        SummaryHit(
            id=r["id"],
            thread_id=r["thread_id"],
            thread_title=r["thread_title"],
            kind=r["kind"],
            content=r["content"],
            score=float(r["rank"]),
        )
        for r in rows
    ]


def semantic_search_comments(
    db: Session, query: str, limit: int = 20
) -> list[CommentHit]:
    embeddings = embed_texts([query])
    if not embeddings or embeddings[0] is None:
        return []
    vec = embeddings[0]
    sql = text(
        f"""
        SELECT {COMMENT_SELECT},
               cf.embedding <=> :vec AS distance
        FROM comment_features cf
        JOIN comments c ON c.id = cf.comment_id
        JOIN threads t ON t.id = c.thread_id
        WHERE cf.embedding IS NOT NULL
        ORDER BY cf.embedding <=> :vec
        LIMIT :limit
        """
    )
    rows = db.execute(
        sql.bindparams(bindparam("vec", type_=Vector(384))),
        {"vec": vec, "limit": limit},
    ).mappings().all()
    return [
        CommentHit(
            id=r["id"],
            thread_id=r["thread_id"],
            thread_title=r["thread_title"],
            author=r["author"],
            body=r["body"],
            score=float(1.0 - r["distance"]),
            distance=float(r["distance"]),
        )
        for r in rows
    ]

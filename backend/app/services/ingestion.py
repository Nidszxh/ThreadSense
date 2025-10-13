from __future__ import annotations

from sqlalchemy.orm import Session

from app.ingest.base import RawThread
from app.models import STATUS_PROCESSING, Comment, Thread


def persist_thread(db: Session, raw: RawThread) -> Thread:
    """Idempotently insert a thread + comments. Returns existing thread on dup."""
    existing = (
        db.query(Thread)
        .filter(Thread.source == raw.source, Thread.source_id == raw.source_id)
        .first()
    )
    if existing is not None:
        return existing

    thread = Thread(
        source=raw.source,
        source_id=raw.source_id,
        title=raw.title,
        url=raw.url,
        author=raw.author,
        status=STATUS_PROCESSING,
    )
    db.add(thread)
    db.flush()

    id_by_index: dict[int, int] = {}
    for index, raw_comment in enumerate(raw.comments):
        comment = Comment(
            thread_id=thread.id,
            parent_id=id_by_index.get(raw_comment.parent_index),
            author=raw_comment.author,
            body=raw_comment.body,
            score=raw_comment.score,
            depth=raw_comment.depth,
            position=index,
            created_at=raw_comment.created_at,
        )
        db.add(comment)
        db.flush()
        id_by_index[index] = comment.id

    db.commit()
    db.refresh(thread)
    return thread

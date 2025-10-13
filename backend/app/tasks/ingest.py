"""Ingestion + local processing tasks.

ingest_thread: fetch + persist, then enqueue process_thread.
process_thread: local NLP (embeddings, keywords, participants), then the LLM chain.
Each task opens its own DB session.
"""

from __future__ import annotations

import logging

from celery import chain
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.ingest import resolve_source
from app.models import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PROCESSING,
    Comment,
    CommentFeature,
    ParticipantStat,
    Thread,
)
from app.nlp.embeddings import embed_texts
from app.nlp.keywords import extract_keywords
from app.nlp.llm_client import get_llm_client
from app.nlp.participants import compute_participants
from app.services.ingestion import persist_thread
from app.tasks.celery_app import celery_app
from app.tasks.summarize import (
    extract_key_points,
    generate_insights,
    summarize_thread,
)

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.ingest_thread")
def ingest_thread(url: str) -> dict:
    source = resolve_source(url)
    raw = source.fetch(url)

    db: Session = SessionLocal()
    try:
        thread = persist_thread(db, raw)
        process_thread.delay(thread.id)
        return {"thread_id": thread.id, "status": thread.status, "title": thread.title}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(name="app.tasks.process_thread")
def process_thread(thread_id: int) -> dict:
    db: Session = SessionLocal()
    try:
        thread = db.get(Thread, thread_id)
        if thread is None:
            return {"thread_id": thread_id, "status": "not_found"}
        thread.status = STATUS_PROCESSING
        db.commit()

        comments = (
            db.query(Comment)
            .filter(Comment.thread_id == thread_id)
            .order_by(Comment.position)
            .all()
        )
        if not comments:
            raise ValueError(f"Thread {thread_id} has no comments")

        texts = [c.body for c in comments]
        embeddings = embed_texts(texts)
        keywords = [extract_keywords(t) for t in texts]

        for comment, embedding, comment_keywords in zip(comments, embeddings, keywords):
            feature = (
                db.query(CommentFeature)
                .filter(CommentFeature.comment_id == comment.id)
                .first()
            )
            if feature is None:
                feature = CommentFeature(comment_id=comment.id)
                db.add(feature)
            feature.embedding = embedding
            feature.keywords = comment_keywords

        participant_rows = compute_participants(
            [
                {
                    "author": c.author,
                    "score": c.score,
                    "depth": c.depth,
                }
                for c in comments
            ]
        )
        db.query(ParticipantStat).filter(ParticipantStat.thread_id == thread_id).delete()
        for row in participant_rows:
            db.add(
                ParticipantStat(
                    thread_id=thread_id,
                    author=row.author,
                    comment_count=row.comment_count,
                    avg_score=row.avg_score,
                    max_depth=row.max_depth,
                    is_root_author=row.is_root_author,
                )
            )
        db.commit()

        if not get_llm_client().available:
            logger.warning("LLM not configured (LLM_API_KEY unset); skipping generation")
            thread.status = STATUS_COMPLETED
            db.commit()
            return {
                "thread_id": thread_id,
                "status": STATUS_COMPLETED,
                "comments": len(comments),
                "participants": len(participant_rows),
                "llm": "skipped",
            }

        thread.status = STATUS_PROCESSING
        db.commit()
        chain(
            summarize_thread.s(thread_id),
            extract_key_points.s(thread_id),
            generate_insights.s(thread_id),
        ).apply_async()
        return {
            "thread_id": thread_id,
            "status": STATUS_PROCESSING,
            "comments": len(comments),
            "participants": len(participant_rows),
            "llm": "enqueued",
        }
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to process thread %s", thread_id)
        thread = db.get(Thread, thread_id)
        if thread is not None:
            thread.status = STATUS_FAILED
            thread.error = str(exc)
            db.commit()
        raise
    finally:
        db.close()

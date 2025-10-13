"""LLM generation tasks, chained: summarize_thread → extract_key_points → generate_insights.

Retries on LLMError with backoff; the last link sets the thread's final status.
Every chain link after the head receives the previous task's result as a
leading positional arg (`previous_result`) — keep it even if unused.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    SUMMARY_KIND_INSIGHTS,
    SUMMARY_KIND_KEY_POINTS,
    SUMMARY_KIND_SUMMARY,
    Thread,
)
from app.nlp.llm_client import LLMError
from app.services.summarization import (
    generate_insights as _generate_insights,
    generate_key_points as _generate_key_points,
    generate_summary as _generate_summary,
)
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

RETRYABLE_ERRORS = (LLMError,)


def _mark_failed(db: Session, thread_id: int, error: str) -> None:
    thread = db.get(Thread, thread_id)
    if thread is not None:
        thread.status = STATUS_FAILED
        thread.error = error
        db.commit()


def _should_mark_failed(self, exc: Exception) -> bool:
    """Mark the thread failed only on the final retry attempt."""
    if not isinstance(exc, RETRYABLE_ERRORS):
        return True
    return self.request.retries >= self.max_retries


@celery_app.task(
    bind=True,
    name="app.tasks.summarize_thread",
    autoretry_for=RETRYABLE_ERRORS,
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def summarize_thread(self, thread_id: int) -> dict:
    db: Session = SessionLocal()
    try:
        result = _generate_summary(db, thread_id)
        logger.info("Summarized thread %s (%s branches)", thread_id, result["branches_covered"])
        return {"thread_id": thread_id, "kind": SUMMARY_KIND_SUMMARY, **result}
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        if _should_mark_failed(self, exc):
            _mark_failed(db, thread_id, str(exc))
        db.close()
        raise


@celery_app.task(
    bind=True,
    name="app.tasks.extract_key_points",
    autoretry_for=RETRYABLE_ERRORS,
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def extract_key_points(self, previous_result: dict, thread_id: int) -> dict:
    db: Session = SessionLocal()
    try:
        result = _generate_key_points(db, thread_id)
        logger.info("Extracted %s key points for thread %s", len(result["points"]), thread_id)
        return {"thread_id": thread_id, "kind": SUMMARY_KIND_KEY_POINTS, **result}
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        if _should_mark_failed(self, exc):
            _mark_failed(db, thread_id, str(exc))
        db.close()
        raise


@celery_app.task(
    bind=True,
    name="app.tasks.generate_insights",
    autoretry_for=RETRYABLE_ERRORS,
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def generate_insights(self, previous_result: dict, thread_id: int) -> dict:
    db: Session = SessionLocal()
    try:
        result = _generate_insights(db, thread_id)
        thread = db.get(Thread, thread_id)
        if thread is not None:
            thread.status = STATUS_COMPLETED
            thread.error = None
            db.commit()
        logger.info("Generated insights for thread %s", thread_id)
        return {"thread_id": thread_id, "kind": SUMMARY_KIND_INSIGHTS, **result}
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        if _should_mark_failed(self, exc):
            _mark_failed(db, thread_id, str(exc))
        db.close()
        raise

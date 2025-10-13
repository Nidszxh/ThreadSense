from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    VALID_STATUSES,
    Comment,
    CommentFeature,
    ParticipantStat,
    Summary,
    Thread,
)
from app.schemas.thread import (
    CommentOut,
    IngestRequest,
    IngestResponse,
    ParticipantOut,
    SummaryOut,
    ThreadDetailOut,
    ThreadOut,
)
from app.tasks.ingest import ingest_thread as ingest_thread_task

router = APIRouter(prefix="/threads", tags=["threads"])


@router.post("/ingest", status_code=202, response_model=IngestResponse)
def ingest(request: IngestRequest) -> IngestResponse:
    try:
        result = ingest_thread_task.delay(request.url)
    except Exception as exc:  # noqa: BLE001  (broker unavailable)
        raise HTTPException(status_code=503, detail=f"Job queue unavailable: {exc}") from exc
    return IngestResponse(task_id=result.id, url=request.url)


@router.get("", response_model=list[ThreadOut])
def list_threads(
    status: str | None = Query(default=None, pattern=f"^({'|'.join(sorted(VALID_STATUSES))})$"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[ThreadOut]:
    query = db.query(Thread)
    if status:
        query = query.filter(Thread.status == status)
    threads = (
        query.order_by(Thread.created_at.desc(), Thread.id.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return [ThreadOut.model_validate(t) for t in threads]


@router.get("/{thread_id}", response_model=ThreadDetailOut)
def get_thread(thread_id: int, db: Session = Depends(get_db)) -> ThreadDetailOut:
    thread = db.get(Thread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    count = db.scalar(
        select(func.count(Comment.id)).where(Comment.thread_id == thread_id)
    )
    detail = ThreadDetailOut.model_validate(thread)
    detail.comment_count = count or 0
    return detail


@router.get("/{thread_id}/comments", response_model=list[CommentOut])
def list_comments(
    thread_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[CommentOut]:
    if db.get(Thread, thread_id) is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    comments = (
        db.query(Comment)
        .filter(Comment.thread_id == thread_id)
        .order_by(Comment.position)
        .limit(limit)
        .offset(offset)
        .all()
    )
    comment_ids = [c.id for c in comments]
    features = {
        f.comment_id: f
        for f in db.query(CommentFeature)
        .filter(CommentFeature.comment_id.in_(comment_ids))
        .all()
    } if comment_ids else {}

    rows: list[CommentOut] = []
    for comment in comments:
        feature = features.get(comment.id)
        rows.append(
            CommentOut(
                id=comment.id,
                thread_id=comment.thread_id,
                parent_id=comment.parent_id,
                author=comment.author,
                body=comment.body,
                score=comment.score,
                depth=comment.depth,
                keywords=list(feature.keywords) if feature and feature.keywords else [],
            )
        )
    return rows


@router.get("/{thread_id}/summaries", response_model=list[SummaryOut])
def list_summaries(thread_id: int, db: Session = Depends(get_db)) -> list[SummaryOut]:
    if db.get(Thread, thread_id) is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    rows = (
        db.query(Summary)
        .filter(Summary.thread_id == thread_id)
        .order_by(Summary.kind)
        .all()
    )
    return [SummaryOut.model_validate(r) for r in rows]


@router.get("/{thread_id}/participants", response_model=list[ParticipantOut])
def list_participants(thread_id: int, db: Session = Depends(get_db)) -> list[ParticipantOut]:
    if db.get(Thread, thread_id) is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    rows = (
        db.query(ParticipantStat)
        .filter(ParticipantStat.thread_id == thread_id)
        .order_by(ParticipantStat.comment_count.desc())
        .all()
    )
    return [ParticipantOut.model_validate(r) for r in rows]

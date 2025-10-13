from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

VALID_STATUSES = {STATUS_PENDING, STATUS_PROCESSING, STATUS_COMPLETED, STATUS_FAILED}


class Thread(Base):
    __tablename__ = "threads"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[str | None] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(512))
    url: Mapped[str] = mapped_column(String(1024))
    author: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default=STATUS_PENDING, index=True)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    comments: Mapped[list[Comment]] = relationship(
        back_populates="thread", cascade="all, delete-orphan", passive_deletes=True
    )
    summaries: Mapped[list[Summary]] = relationship(
        back_populates="thread", cascade="all, delete-orphan", passive_deletes=True
    )
    participant_stats: Mapped[list[ParticipantStat]] = relationship(
        back_populates="thread", cascade="all, delete-orphan", passive_deletes=True
    )

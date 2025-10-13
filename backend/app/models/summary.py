from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.thread import Thread

SUMMARY_KIND_SUMMARY = "summary"
SUMMARY_KIND_KEY_POINTS = "key_points"
SUMMARY_KIND_INSIGHTS = "insights"


class Summary(Base):
    __tablename__ = "summaries"
    __table_args__ = (
        UniqueConstraint("thread_id", "kind", name="uq_summaries_thread_kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int] = mapped_column(
        ForeignKey("threads.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(32))
    content: Mapped[dict] = mapped_column(JSONB)
    model: Mapped[str | None] = mapped_column(String(128))
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    thread: Mapped[Thread] = relationship(back_populates="summaries")

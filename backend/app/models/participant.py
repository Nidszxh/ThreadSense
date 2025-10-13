from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.thread import Thread


class ParticipantStat(Base):
    __tablename__ = "participant_stats"
    __table_args__ = (
        UniqueConstraint(
            "thread_id", "author", name="uq_participant_stats_thread_author"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int] = mapped_column(
        ForeignKey("threads.id", ondelete="CASCADE"), index=True
    )
    author: Mapped[str] = mapped_column(String(128))
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_score: Mapped[float] = mapped_column(Float, default=0.0)
    max_depth: Mapped[int] = mapped_column(Integer, default=0)
    is_root_author: Mapped[bool] = mapped_column(Boolean, default=False)

    thread: Mapped[Thread] = relationship(back_populates="participant_stats")

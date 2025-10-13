from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.thread import Thread

EMBEDDING_DIM = 384


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (
        Index("ix_comments_thread_id_position", "thread_id", "position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int] = mapped_column(
        ForeignKey("threads.id", ondelete="CASCADE")
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), index=True
    )
    author: Mapped[str | None] = mapped_column(String(128))
    body: Mapped[str] = mapped_column(Text, default="")
    depth: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[int] = mapped_column(Integer, default=0)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    thread: Mapped[Thread] = relationship(back_populates="comments")
    feature: Mapped[CommentFeature | None] = relationship(
        back_populates="comment",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class CommentFeature(Base):
    __tablename__ = "comment_features"

    id: Mapped[int] = mapped_column(primary_key=True)
    comment_id: Mapped[int] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), unique=True
    )
    keywords: Mapped[list] = mapped_column(JSONB, default=list)
    embedding: Mapped[list | None] = mapped_column(Vector(EMBEDDING_DIM))
    sentiment: Mapped[str | None] = mapped_column(String(32))

    comment: Mapped[Comment] = relationship(back_populates="feature")

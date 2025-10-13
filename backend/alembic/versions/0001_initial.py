"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-12

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "threads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(128), nullable=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("url", sa.String(1024), nullable=False),
        sa.Column("author", sa.String(128), nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_threads_status", "threads", ["status"])
    op.create_index("ix_threads_created_at", "threads", ["created_at"])
    op.create_index("ix_threads_source_id", "threads", ["source_id"])

    op.create_table(
        "comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "thread_id",
            sa.Integer(),
            sa.ForeignKey("threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            sa.Integer(),
            sa.ForeignKey("comments.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("author", sa.String(128), nullable=True),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_comments_thread_id_position", "comments", ["thread_id", "position"]
    )
    op.create_index("ix_comments_parent_id", "comments", ["parent_id"])

    op.create_table(
        "comment_features",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "comment_id",
            sa.Integer(),
            sa.ForeignKey("comments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "keywords",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("sentiment", sa.String(32), nullable=True),
    )
    op.create_unique_constraint(
        "uq_comment_features_comment_id", "comment_features", ["comment_id"]
    )

    op.create_table(
        "summaries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "thread_id",
            sa.Integer(),
            sa.ForeignKey("threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("content", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_summaries_thread_id", "summaries", ["thread_id"])
    op.create_unique_constraint(
        "uq_summaries_thread_kind", "summaries", ["thread_id", "kind"]
    )

    op.create_table(
        "participant_stats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "thread_id",
            sa.Integer(),
            sa.ForeignKey("threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("author", sa.String(128), nullable=False),
        sa.Column("comment_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("max_depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "is_root_author", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.create_index(
        "ix_participant_stats_thread_id", "participant_stats", ["thread_id"]
    )
    op.create_unique_constraint(
        "uq_participant_stats_thread_author",
        "participant_stats",
        ["thread_id", "author"],
    )


def downgrade() -> None:
    op.drop_table("participant_stats")
    op.drop_table("summaries")
    op.drop_table("comment_features")
    op.drop_table("comments")
    op.drop_table("threads")
    op.execute("DROP EXTENSION IF EXISTS vector")

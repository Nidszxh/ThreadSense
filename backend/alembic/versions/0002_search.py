"""keyword (FTS) search indexes

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-13

"""

from collections.abc import Sequence

import sqlalchemy as sa  # noqa: F401
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_comments_body_fts ON comments "
        "USING gin (to_tsvector('english', body))"
    )
    op.execute(
        "CREATE INDEX ix_summaries_content_fts ON summaries "
        "USING gin (to_tsvector('english', content::text))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_summaries_content_fts")
    op.execute("DROP INDEX IF EXISTS ix_comments_body_fts")

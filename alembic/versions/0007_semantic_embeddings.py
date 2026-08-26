"""Kolom embedding vektor utk RAG semantik (Fase 2) - mental_health_topics & content_library.

Vektor disimpan sbg JSON float array (MySQL 8 tdk punya tipe vector native).
NULL = belum ter-embed; retrieval leksikal tetap jalan tanpa embedding.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _dt6() -> sa.DateTime:
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def upgrade() -> None:
    for table in ("mental_health_topics", "content_library"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("embedding", sa.JSON(), nullable=True))
            batch.add_column(sa.Column("embedded_at", _dt6(), nullable=True))


def downgrade() -> None:
    for table in ("mental_health_topics", "content_library"):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("embedded_at")
            batch.drop_column("embedding")

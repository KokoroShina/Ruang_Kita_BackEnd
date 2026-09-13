"""Kolom video_url utk topik — video penjelasan YouTube (fitur topik).

Diisi admin lewat form topik (URL YouTube divalidasi schema). Di-embed di
halaman detail topik sebagai penjelasan lanjutan setelah konten edukatif.
Nullable — topik lama tetap valid tanpa video.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("mental_health_topics") as batch:
        batch.add_column(sa.Column("video_url", sa.String(500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("mental_health_topics") as batch:
        batch.drop_column("video_url")

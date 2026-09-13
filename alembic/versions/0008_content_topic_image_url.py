"""Kolom image_url utk thumbnail konten & topik (admin Temukan).

Hybrid: nilai berupa URL eksternal (mis. thumbnail YouTube) ATAU path aset
lokal hasil upload (disajikan backend lewat /media). Nullable - konten
lama tetap valid tanpa gambar.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("content_library", "mental_health_topics"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("image_url", sa.String(500), nullable=True))


def downgrade() -> None:
    for table in ("content_library", "mental_health_topics"):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("image_url")

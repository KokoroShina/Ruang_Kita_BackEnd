"""Tambah crisis_flagged di journal_entries

Deteksi krisis di konten jurnal harus bisa mengarahkan ke jalur berbeda
(sementara: ai_insight diisi pesan dukungan standar + flag tersimpan utk audit).

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "journal_entries",
        sa.Column("crisis_flagged", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("journal_entries", "crisis_flagged")

"""Kembalikan NOT NULL pada kolom timestamp (residual drift dari 0003).

Migration 0003 memakai batch_alter_table untuk mengubah tipe DATETIME -> DATETIME(6);
proses tersebut menghapus atribut NOT NULL pada beberapa kolom sehingga
`alembic check` melaporkan drift nullable terhadap metadata model.
Migration ini menyelaraskan DB kembali dengan model (semua timestamp NOT NULL).

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _dt6() -> sa.DateTime:
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


# (table, column, server_default) — semua timestamp NOT NULL + default mikrodetik
TARGETS: list[tuple[str, str]] = [
    ("users", "created_at"),
    ("users", "updated_at"),
    ("journal_entries", "created_at"),
    ("journal_entries", "updated_at"),
    ("mood_logs", "logged_at"),
    ("mood_logs", "created_at"),
    ("mood_logs", "updated_at"),
    ("chat_sessions", "created_at"),
    ("chat_sessions", "updated_at"),
    ("chat_messages", "created_at"),
    ("chat_messages", "updated_at"),
    ("content_library", "created_at"),
    ("content_library", "updated_at"),
    ("ai_usage_log", "created_at"),
]


def upgrade() -> None:
    for table, column in TARGETS:
        with op.batch_alter_table(table) as batch:
            batch.alter_column(
                column,
                existing_type=_dt6(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP(6)"),
            )


def downgrade() -> None:
    # Tidak dikembalikan ke nullable=True — drift itu tidak pernah disengaja.
    pass

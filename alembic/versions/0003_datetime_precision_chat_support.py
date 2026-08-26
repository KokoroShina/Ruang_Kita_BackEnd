"""Presisi mikrodetik utk semua DATETIME + widen provider

- DATETIME -> DATETIME(6): urutan pesan chat dalam detik sama jadi deterministik
  (UUID PK tidak bisa dipakai sorting)
- server_default CURRENT_TIMESTAMP -> CURRENT_TIMESTAMP(6) agar fraksi detik terisi
- chat_messages.provider VARCHAR(32) -> VARCHAR(128) utk slug model OpenRouter

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# {tabel: (kolom_berdefault, kolom_tanpa_default)}
TABLE_COLUMNS: dict[str, tuple[list[str], list[str]]] = {
    "users": (["created_at", "updated_at"], ["consent_accepted_at"]),
    "journal_entries": (["created_at", "updated_at"], []),
    "mood_logs": (["created_at", "updated_at", "logged_at"], []),
    "chat_sessions": (["created_at", "updated_at"], ["last_message_at"]),
    "chat_messages": (["created_at", "updated_at"], []),
    "content_library": (["created_at", "updated_at"], ["published_at"]),
    "ai_usage_log": (["created_at"], []),
}


def _upgrade_datetimes(direction: str) -> None:
    for table, (with_default, without_default) in TABLE_COLUMNS.items():
        for col in with_default:
            kwargs = dict(
                existing_type=sa.DateTime(),
                type_=mysql.DATETIME(fsp=6),
                existing_server_default=sa.text("CURRENT_TIMESTAMP"),
            )
            if direction == "up":
                kwargs["server_default"] = sa.text("CURRENT_TIMESTAMP(6)")
            else:
                kwargs["server_default"] = sa.text("CURRENT_TIMESTAMP")
            op.alter_column(table, col, **kwargs)
        for col in without_default:
            op.alter_column(
                table, col, existing_type=sa.DateTime(), type_=mysql.DATETIME(fsp=6)
            )


def upgrade() -> None:
    _upgrade_datetimes("up")
    op.alter_column(
        "chat_messages",
        "provider",
        existing_type=sa.String(length=32),
        type_=sa.String(length=128),
    )


def downgrade() -> None:
    op.alter_column(
        "chat_messages",
        "provider",
        existing_type=sa.String(length=128),
        type_=sa.String(length=32),
    )
    _upgrade_datetimes("down")

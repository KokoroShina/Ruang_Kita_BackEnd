"""Tambah tabel ai_usage_log - logging pemakaian AI Gateway

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_log",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("endpoint_type", sa.String(length=32), nullable=False),
        sa.Column("model_requested", sa.String(length=128), nullable=False),
        sa.Column("model_used", sa.String(length=128), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_type", sa.String(length=64), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("finish_reason", sa.String(length=32), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_ai_usage_log_user_id_users",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_ai_usage_log_user_id", "ai_usage_log", ["user_id"])
    op.create_index("ix_ai_usage_log_created_at", "ai_usage_log", ["created_at"])


def downgrade() -> None:
    op.drop_table("ai_usage_log")

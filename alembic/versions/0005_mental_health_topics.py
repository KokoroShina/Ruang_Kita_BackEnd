"""Tabel mental_health_topics - ensiklopedia kesehatan mental (psikoedukasi).

Konten terkurasi manual via seed/import; dibaca user lewat /topics,
dikelola admin lewat /admin/topics (gate ADMIN_EMAILS).

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _dt6() -> sa.DateTime:
    """DATETIME(fsp=6) konsisten dengan DateTimeMicro di app.db.base."""
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def upgrade() -> None:
    op.create_table(
        "mental_health_topics",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("alt_names", sa.JSON(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("signs_symptoms", sa.JSON(), nullable=False),
        sa.Column("causes_risk_factors", sa.Text(), nullable=True),
        sa.Column("coping_treatment", sa.Text(), nullable=True),
        sa.Column("myths_facts", sa.JSON(), nullable=False),
        sa.Column("when_to_seek_help", sa.Text(), nullable=True),
        sa.Column("support_resources", sa.JSON(), nullable=False),
        sa.Column("related_topic_slugs", sa.JSON(), nullable=False),
        sa.Column("sources", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("is_published", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("published_at", _dt6(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", _dt6(), server_default=sa.text("CURRENT_TIMESTAMP(6)"), nullable=False),
        sa.Column("updated_at", _dt6(), server_default=sa.text("CURRENT_TIMESTAMP(6)"), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_mental_health_topics_created_by_users",
            ondelete="SET NULL",
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_mental_health_topics_slug", "mental_health_topics", ["slug"], unique=True
    )
    op.create_index(
        "ix_mental_health_topics_category", "mental_health_topics", ["category"]
    )


def downgrade() -> None:
    op.drop_table("mental_health_topics")

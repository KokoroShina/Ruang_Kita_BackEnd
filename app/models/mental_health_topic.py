import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    false,
)
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, DateTimeMicro, TimestampMixin, UUIDPrimaryKeyMixin


class MentalHealthTopic(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Entri ensiklopedia kesehatan mental — psikoedukasi non-diagnostik.

    Konten terkurasi manual (seed/import JSON), dibaca user lewat /topics.
    Nanti jadi bagian knowledge base RAG (context_snippets hook sudah siap).
    """

    __tablename__ = "mental_health_topics"

    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Istilah populer/lain (mis. "gangguan stres pascatrauma" untuk PTSD)
    alt_names: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list)

    # mood | anxiety | personality | trauma | eating | burnout | other
    category: Mapped[str] = mapped_column(
        String(32), default="other", nullable=False, index=True
    )

    summary: Mapped[str] = mapped_column(Text, nullable=False)
    signs_symptoms: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list)
    causes_risk_factors: Mapped[str | None] = mapped_column(Text)
    coping_treatment: Mapped[str | None] = mapped_column(Text)

    # [{"myth": "...", "fact": "..."}]
    myths_facts: Mapped[list[dict]] = mapped_column(JSON, default=list)
    when_to_seek_help: Mapped[str | None] = mapped_column(Text)

    # [{"name": "SEJIWA", "contact": "119 ext. 8", "description": "..."}]
    support_resources: Mapped[list[dict]] = mapped_column(JSON, default=list)

    related_topic_slugs: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list)

    sources: Mapped[str | None] = mapped_column(Text)

    language: Mapped[str] = mapped_column(String(8), default="id", nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    published_at: Mapped[datetime | None] = mapped_column(DateTimeMicro)

    # RAG semantik (Fase 2): vektor JSON float array; NULL = belum ter-embed
    embedding: Mapped[list | None] = mapped_column(JSON)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTimeMicro)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    def __repr__(self) -> str:
        return f"<MentalHealthTopic id={self.id} slug={self.slug!r} published={self.is_published}>"

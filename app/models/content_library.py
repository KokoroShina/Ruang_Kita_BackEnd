import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    false,
)
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, DateTimeMicro, TimestampMixin, UUIDPrimaryKeyMixin


class ContentType(str, enum.Enum):
    ARTICLE = "article"
    VIDEO = "video"
    AUDIO = "audio"
    EXERCISE = "exercise"


class ContentLibrary(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Konten psikoedukasi terkurasi manual — fondasi pilar Temukan."""

    __tablename__ = "content_library"

    slug: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    summary: Mapped[str | None] = mapped_column(Text)
    content_body: Mapped[str | None] = mapped_column(Text)

    content_type: Mapped[str] = mapped_column(
        String(32), default=ContentType.ARTICLE.value, nullable=False
    )
    # MutableList agar mutasi list terdeteksi SQLAlchemy; JSON portable lintas DB
    topics: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list)

    source_url: Mapped[str | None] = mapped_column(String(500))
    duration_minutes: Mapped[int | None] = mapped_column(SmallInteger)

    language: Mapped[str] = mapped_column(String(8), default="id", nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    published_at: Mapped[datetime | None] = mapped_column(DateTimeMicro)

    # RAG semantik (Fase 2): vektor JSON float array; NULL = belum ter-embed
    embedding: Mapped[list | None] = mapped_column(JSON)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTimeMicro)

    # Kurator (admin/konten team) — FK longgar ke users
    curated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    def __repr__(self) -> str:
        return f"<ContentLibrary id={self.id} slug={self.slug!r}>"

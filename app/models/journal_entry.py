import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class JournalEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "journal_entries"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Kolom insight AI (pilar Kenali) — diisi belakangan oleh AI Gateway
    ai_insight: Mapped[str | None] = mapped_column(Text)

    # Crisis detection pada konten jurnal -> jalur dukungan, bukan analisis biasa
    crisis_flagged: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="journal_entries")

    def __repr__(self) -> str:
        return f"<JournalEntry id={self.id} user_id={self.user_id}>"

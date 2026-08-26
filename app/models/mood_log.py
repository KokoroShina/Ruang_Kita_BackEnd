import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import SERVER_NOW_6, Base, DateTimeMicro, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class MoodSource(str, enum.Enum):
    ONBOARDING_SELFCHECK = "onboarding_selfcheck"
    MANUAL = "manual"
    JOURNAL = "journal"
    CHAT = "chat"


class MoodLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mood_logs"
    __table_args__ = (
        CheckConstraint("mood_score IS NULL OR mood_score BETWEEN 1 AND 5", name="mood_score_range"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # Skala numerik 1-5 (opsional) + label bebas (mis. "cemas", "senang") — fleksibel untuk evolusi skema mood
    mood_score: Mapped[int | None] = mapped_column(SmallInteger)
    mood_label: Mapped[str | None] = mapped_column(String(64))

    note: Mapped[str | None] = mapped_column(Text)

    source: Mapped[str] = mapped_column(
        String(32), default=MoodSource.MANUAL.value, nullable=False
    )

    # logged_at terpisah dari created_at → mendukung backfill/log antizip waktu manual
    logged_at: Mapped[datetime] = mapped_column(
        DateTimeMicro, server_default=SERVER_NOW_6, index=True, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="mood_logs")

    def __repr__(self) -> str:
        return f"<MoodLog id={self.id} user_id={self.user_id} score={self.mood_score}>"

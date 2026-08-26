import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, DateTimeMicro, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class ChatSessionStatus(str, enum.Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    ARCHIVED = "archived"


class ChatSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chat_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(32), default=ChatSessionStatus.ACTIVE.value, nullable=False
    )

    # Crisis detection (indikasi self-harm/risiko tinggi) → jalur khusus, bukan AI biasa
    crisis_flagged: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )

    last_message_at: Mapped[datetime | None] = mapped_column(DateTimeMicro, index=True)

    user: Mapped["User"] = relationship(back_populates="chat_sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ChatMessage.created_at",
    )

    def __repr__(self) -> str:
        return f"<ChatSession id={self.id} user_id={self.user_id} status={self.status!r}>"


class ChatMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (CheckConstraint("sender_role IN ('user', 'assistant')", name="sender_role_valid"),)

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    sender_role: Mapped[str] = mapped_column(String(16), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Provider AI yang menghasilkan pesan assistant (gemini/groq) — observability AI Gateway
    provider: Mapped[str | None] = mapped_column(String(128))

    # Flag per-pesan hasil crisis detection — memudahkan audit & review
    crisis_flagged: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )

    session: Mapped["ChatSession"] = relationship(back_populates="messages")

    def __repr__(self) -> str:
        return f"<ChatMessage id={self.id} role={self.sender_role!r}>"

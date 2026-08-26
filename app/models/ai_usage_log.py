import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import SERVER_NOW_6, Base, DateTimeMicro, UUIDPrimaryKeyMixin


class AIUsageLog(UUIDPrimaryKeyMixin, Base):
    """Log tiap percobaan pemanggilan AI Gateway (append-only, tanpa updated_at).

    Satu baris PER ATTEMPT (bukan per request) — memudahkan melihat pola
    rate limit per model: model mana yang sering 429 dan kapan.
    """

    __tablename__ = "ai_usage_log"

    endpoint_type: Mapped[str] = mapped_column(String(32), nullable=False)  # test|chat|journal_analysis
    model_requested: Mapped[str] = mapped_column(String(128), nullable=False)
    model_used: Mapped[str | None] = mapped_column(String(128))  # isi saat sukses

    success: Mapped[bool] = mapped_column(Boolean, nullable=False)

    error_type: Mapped[str | None] = mapped_column(String(64))
    # rate_limit | timeout | provider_error | auth_error |
    # crisis_input_detected | crisis_output_detected
    error_detail: Mapped[str | None] = mapped_column(Text)

    latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    finish_reason: Mapped[str | None] = mapped_column(String(32))

    # Pemicu request — nullable agar log tetap hidup walau user terhapus (audit)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTimeMicro, server_default=SERVER_NOW_6, index=True, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<AIUsageLog model={self.model_used or self.model_requested!r} "
            f"success={self.success} type={self.endpoint_type!r}>"
        )

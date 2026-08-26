import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MoodLogCreate(BaseModel):
    mood_score: int = Field(ge=1, le=5, description="1=sangat buruk ... 5=sangat baik")
    mood_label: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=5000)
    logged_at: datetime | None = Field(
        default=None,
        description="Opsional (backfill); default = sekarang UTC. Ditolak bila di masa depan.",
    )

    @model_validator(mode="after")
    def _no_future_log(self) -> "MoodLogCreate":
        if self.logged_at is not None:
            from datetime import datetime as _dt
            from datetime import timezone as _tz

            now = _dt.now(_tz.utc).replace(tzinfo=None)
            if self.logged_at.replace(tzinfo=None) > now:
                raise ValueError("logged_at tidak boleh di masa depan")
        return self


class MoodLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mood_score: int | None
    mood_label: str | None
    note: str | None
    source: str
    logged_at: datetime
    created_at: datetime


class DailyTrendPoint(BaseModel):
    date: date
    avg_score: float
    count: int


class LabelCount(BaseModel):
    label: str
    count: int


class MoodStatsResponse(BaseModel):
    period_days: int
    total_logs: int
    avg_score: float | None
    daily_trend: list[DailyTrendPoint] = []
    score_distribution: dict[str, int]
    current_streak_days: int
    top_labels: list[LabelCount] = []


class MoodLogUpdate(BaseModel):
    """Edit log milik sendiri — hanya field konten; source & logged_at tidak diubah di sini."""

    mood_score: int | None = Field(default=None, ge=1, le=5)
    mood_label: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=5000)

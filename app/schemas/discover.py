import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ===== Content library (browse + admin CRUD) =====


class ContentItemCreate(BaseModel):
    slug: str = Field(
        min_length=2,
        max_length=160,
        pattern=r"^[A-Za-z0-9]+(-[A-Za-z0-9]+)*$",
        description="URL-safe; otomatis lowercase. Contoh: napas-478",
    )
    title: str = Field(min_length=1, max_length=255)
    summary: str | None = Field(default=None, max_length=2000)
    content_body: str | None = Field(default=None, max_length=20000)
    content_type: str = Field(default="article", max_length=32)
    topics: list[str] = Field(default_factory=list, max_length=20)
    source_url: str | None = Field(default=None, max_length=500)
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    language: str = Field(default="id", min_length=2, max_length=8)
    is_published: bool = False


class ContentItemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    summary: str | None = Field(default=None, max_length=2000)
    content_body: str | None = Field(default=None, max_length=20000)
    content_type: str | None = Field(default=None, max_length=32)
    topics: list[str] | None = Field(default=None, max_length=20)
    source_url: str | None = Field(default=None, max_length=500)
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    language: str | None = Field(default=None, min_length=2, max_length=8)
    is_published: bool | None = None


class ContentItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    title: str
    summary: str | None
    content_body: str | None
    content_type: str
    topics: list[str]
    source_url: str | None
    duration_minutes: int | None
    language: str
    is_published: bool
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


# ===== Rekomendasi (rule-based) =====


class RecommendationReason(BaseModel):
    kind: str  # journal_topic_match | mood_label | low_mood_trend | general_wellbeing
    detail: str


class TopicRecommendation(BaseModel):
    slug: str
    name: str
    category: str
    summary: str
    score: int
    reasons: list[RecommendationReason] = []


class ContentRecommendation(BaseModel):
    slug: str
    title: str
    content_type: str
    summary: str | None
    duration_minutes: int | None
    matched_topics: list[str] = []


class DiscoverResponse(BaseModel):
    based_on: list[str] = []
    topics: list[TopicRecommendation] = []
    content: list[ContentRecommendation] = []

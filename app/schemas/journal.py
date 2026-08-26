import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class JournalEntryCreate(BaseModel):
    content: str = Field(min_length=1, max_length=20000)
    title: str | None = Field(default=None, max_length=200)


class JournalEntryUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    content: str | None = Field(default=None, min_length=1, max_length=20000)


class JournalEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    content: str
    ai_insight: str | None
    crisis_flagged: bool
    created_at: datetime
    updated_at: datetime


class JournalAnalyzeRequest(BaseModel):
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=600, ge=1, le=2000)


class JournalAnalyzeResponse(BaseModel):
    crisis_detected: bool = False
    entry: JournalEntryRead
    model_used: str | None = None
    latency_ms: int | None = None
    attempts: list[dict] = []
    grounded_topics: list[str] = []  # RAG: topik yang di-grounding ke analisis

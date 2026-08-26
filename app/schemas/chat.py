import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatSessionCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sender_role: str
    content: str
    crisis_flagged: bool
    provider: str | None
    created_at: datetime


class ChatSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    status: str
    crisis_flagged: bool
    last_message_at: datetime | None
    created_at: datetime


class ChatSessionDetailRead(ChatSessionRead):
    messages: list[ChatMessageRead] = []


class ChatSendMessage(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=2000)


class ChatSendResponse(BaseModel):
    crisis_detected: bool = False
    user_message: ChatMessageRead
    assistant_message: ChatMessageRead | None = None
    model_used: str | None = None
    latency_ms: int | None = None
    attempts: list[dict] = []
    grounded_topics: list[str] = []  # RAG: topik published yang disebut user & dipakai grounding

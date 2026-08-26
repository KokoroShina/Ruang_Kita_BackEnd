from pydantic import BaseModel, Field


class AITestRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=400, ge=1, le=2000)


class AttemptRead(BaseModel):
    model: str
    ok: bool
    error: str | None = None


class AITestResponse(BaseModel):
    crisis_detected: bool = False
    response: str | None = None
    model_used: str | None = None
    attempts: list[AttemptRead] = []
    latency_ms: int | None = None
    detail: str | None = None  # diisi saat crisis_detected / pesan khusus lainnya

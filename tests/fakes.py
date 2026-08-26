"""AI palsu deterministik untuk menggantikan OpenRouter gateway dalam test.

Kontrak disamakan persis dengan implementasi asli:
- RecordingFakeAI menggantikan `generate_text` (di-patch pada modul PEMAKAI:
  app.services.chat_service / app.services.journal_service).
- fake_stream_text menggantikan `app.services.ai.router.stream_text`
  (yield tuple (kind, payload): model/delta/crisis/done).
"""

from dataclasses import dataclass, field

from app.services.ai.router import AttemptInfo, GatewayResult


@dataclass
class RecordingFakeAI:
    """generate_text palsu: balas konten tetap + rekam semua pemanggilan."""

    reply: str = "Aku dengar kamu, dan perasaanmu itu valid."
    model_used: str = "fake-model:test"
    calls: list = field(default_factory=list)

    async def __call__(
        self,
        *,
        messages,
        endpoint_type="chat",
        user_id=None,
        temperature=None,
        max_tokens=None,
    ) -> GatewayResult:
        self.calls.append({"messages": messages, "endpoint_type": endpoint_type})
        return GatewayResult(
            content=self.reply,
            model_used=self.model_used,
            attempts=[AttemptInfo(model=self.model_used, ok=True)],
            latency_ms=5,
            finish_reason="stop",
            input_tokens=10,
            output_tokens=10,
        )

    @property
    def called(self) -> bool:
        return len(self.calls) > 0

    @property
    def last_messages(self):
        return self.calls[-1]["messages"] if self.calls else None


def fake_stream_text(*pieces: str, crisis_at: int | None = None):
    """stream_text palsu. crisis_at=i -> event crisis terjadi SEBELUM piece ke-i.

    crisis_at=0            -> crisis tanpa delta apa pun.
    crisis_at=len(pieces)  -> semua delta keluar dulu, lalu crisis (partial dibuang server).
    """

    async def _gen(*args, **kwargs):
        yield ("model", {"model": "fake-model:test"})
        for i, piece in enumerate(pieces):
            if crisis_at is not None and i == crisis_at:
                yield ("crisis", {"attempts": []})
                return
            yield ("delta", {"text": piece})
        if crisis_at is not None:
            yield ("crisis", {"attempts": []})
            return
        yield (
            "done",
            {"model_used": "fake-model:test", "latency_ms": 7, "attempts": []},
        )

    return _gen


def failing_generate_text(exc_factory):
    """generate_text palsu yang selalu raise (mis. AIGatewayError) — utk test jalur gagal."""

    async def _fail(*args, **kwargs):
        raise exc_factory()

    return _fail

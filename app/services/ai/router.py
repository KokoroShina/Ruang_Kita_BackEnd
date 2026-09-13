"""AI Router — pemilihan model, fallback, guardrail hooks, usage logging.

Alur generate_text():
    1. detect_crisis(INPUT)   -> flagged? log + raise CrisisDetectedError (jalur khusus)
    2. detect_offtopic(INPUT) -> flagged? log + raise OffTopicDetectedError (chat saja)
    3. Coba model default -> fallback berurutan saat 429/error (urutan dari .env)
       - AuthError (key invalid) : fail-fast, tidak di-fallback
    4. detect_crisis(OUTPUT)  -> flagged? log + raise CrisisDetectedError
    5. apply_disclaimer()     -> WAJIB sebelum konten dikembalikan

Setiap attempt (sukses maupun gagal) dicatat ke tabel ai_usage_log lewat
session DB terpisah — logging tidak boleh mengganggu/meng-commit transaksi caller.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.ai_usage_log import AIUsageLog
from app.services.ai.guardrails import (
    apply_disclaimer,
    detect_crisis,
    detect_offtopic,
)
from app.services.ai.openrouter_client import (
    OpenRouterAuthError,
    OpenRouterError,
    OpenRouterProviderError,
    OpenRouterRateLimitError,
    OpenRouterTimeoutError,
    get_openrouter_client,
)

logger = logging.getLogger(__name__)


class AIGatewayError(Exception):
    """Semua model kandidat gagal — endpoint pemanggil harus tampilkan pesan wajar."""


class AIConfigurationError(Exception):
    """Konfigurasi gateway bermasalah (mis. key invalid) — bukan masalah model."""


class CrisisDetectedError(Exception):
    """Input/output mengandung indikasi risiko tinggi -> jalur dukungan khusus."""

    def __init__(self, source: str, matched_keyword: str | None = None) -> None:
        self.source = source  # "input" | "output"
        self.matched_keyword = matched_keyword
        super().__init__(f"Crisis signal detected on {source}")


class OffTopicDetectedError(Exception):
    """Input di luar scope refleksi (chat) -> balasan SCOPE_REDIRECT_TEXT tanpa LLM."""

    def __init__(self, matched_pattern: str | None = None) -> None:
        self.matched_pattern = matched_pattern
        super().__init__(f"Off-topic request detected: {matched_pattern!r}")


@dataclass(slots=True)
class AttemptInfo:
    model: str
    ok: bool
    error: str | None = None


@dataclass(slots=True)
class GatewayResult:
    content: str
    model_used: str
    attempts: list[AttemptInfo] = field(default_factory=list)
    latency_ms: int = 0
    finish_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


def _last_user_text(messages: list[dict[str, str]]) -> str | None:
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content") or "")
    return None


async def _log_attempt(
    *,
    endpoint_type: str,
    model_requested: str,
    success: bool,
    user_id: uuid.UUID | None = None,
    model_used: str | None = None,
    error_type: str | None = None,
    error_detail: str | None = None,
    latency_ms: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    finish_reason: str | None = None,
) -> None:
    """Tulis satu baris ai_usage_log. Gagal logging TIDAK BOLEH merusak flow user."""
    try:
        async with AsyncSessionLocal() as session:
            session.add(
                AIUsageLog(
                    endpoint_type=endpoint_type,
                    model_requested=model_requested,
                    model_used=model_used,
                    success=success,
                    error_type=error_type,
                    error_detail=error_detail[:500] if error_detail else None,
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    finish_reason=finish_reason,
                    user_id=user_id,
                )
            )
            await session.commit()
    except Exception:  # noqa: BLE001
        logger.warning("Gagal menulis ai_usage_log", exc_info=True)


async def generate_text(
    *,
    messages: list[dict[str, str]],
    endpoint_type: str = "chat",
    user_id: uuid.UUID | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> GatewayResult:
    """Fungsi utama AI Gateway. Raise: CrisisDetectedError / OffTopicDetectedError / AIConfigurationError / AIGatewayError."""
    # ---- 1. Guardrail INPUT -------------------------------------------------
    crisis = detect_crisis(_last_user_text(messages))
    if crisis.flagged:
        await _log_attempt(
            endpoint_type=endpoint_type,
            model_requested=settings.AI_MODEL_DEFAULT,
            success=False,
            error_type="crisis_input_detected",
            error_detail=f"keyword={crisis.matched_keyword!r}",
            user_id=user_id,
        )
        raise CrisisDetectedError(source="input", matched_keyword=crisis.matched_keyword)

    # ---- 1b. Scope enforcement (chat saja; jurnal dianalisis normal) ---------
    if endpoint_type == "chat":
        offtopic = detect_offtopic(_last_user_text(messages))
        if offtopic.flagged:
            await _log_attempt(
                endpoint_type=endpoint_type,
                model_requested=settings.AI_MODEL_DEFAULT,
                success=False,
                error_type="offtopic_input_detected",
                error_detail=f"pattern={offtopic.matched_pattern!r}",
                user_id=user_id,
            )
            raise OffTopicDetectedError(matched_pattern=offtopic.matched_pattern)

    client = get_openrouter_client()
    attempts: list[AttemptInfo] = []
    last_error: Exception | None = None

    for model in settings.ai_model_candidates:
        started = time.perf_counter()
        try:
            raw = await client.chat_completion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except OpenRouterAuthError as exc:
            attempts.append(AttemptInfo(model=model, ok=False, error=str(exc)))
            await _log_attempt(
                endpoint_type=endpoint_type, model_requested=model, success=False,
                error_type="auth_error", error_detail=str(exc), user_id=user_id,
            )
            raise AIConfigurationError(str(exc)) from exc
        except OpenRouterRateLimitError as exc:
            attempts.append(AttemptInfo(model=model, ok=False, error=str(exc)[:300]))
            last_error = exc
            await _log_attempt(
                endpoint_type=endpoint_type, model_requested=model, success=False,
                error_type="rate_limit", error_detail=str(exc)[:500], user_id=user_id,
            )
            continue
        except OpenRouterTimeoutError as exc:
            attempts.append(AttemptInfo(model=model, ok=False, error=str(exc)[:300]))
            last_error = exc
            await _log_attempt(
                endpoint_type=endpoint_type, model_requested=model, success=False,
                error_type="timeout", error_detail=str(exc)[:500], user_id=user_id,
            )
            continue
        except Exception as exc:  # provider error lain (konten kosong, 5xx, jaringan)
            attempts.append(AttemptInfo(model=model, ok=False, error=f"{type(exc).__name__}: {exc}"[:300]))
            last_error = exc
            await _log_attempt(
                endpoint_type=endpoint_type, model_requested=model, success=False,
                error_type="provider_error", error_detail=f"{type(exc).__name__}: {exc}"[:500],
                user_id=user_id,
            )
            continue

        latency_ms = int((time.perf_counter() - started) * 1000)

        # ---- 3. Guardrail OUTPUT -------------------------------------------
        out_crisis = detect_crisis(raw["content"])
        if out_crisis.flagged:
            attempts.append(AttemptInfo(model=model, ok=True))
            await _log_attempt(
                endpoint_type=endpoint_type, model_requested=model, success=False,
                model_used=model, latency_ms=latency_ms, finish_reason=raw["finish_reason"],
                input_tokens=raw["usage"].get("prompt_tokens"),
                output_tokens=raw["usage"].get("completion_tokens"),
                error_type="crisis_output_detected",
                error_detail=f"keyword={out_crisis.matched_keyword!r}",
                user_id=user_id,
            )
            raise CrisisDetectedError(source="output", matched_keyword=out_crisis.matched_keyword)

        # ---- 4. Disclaimer layer -------------------------------------------
        final_content = apply_disclaimer(raw["content"], endpoint_type)

        attempts.append(AttemptInfo(model=model, ok=True))
        await _log_attempt(
            endpoint_type=endpoint_type, model_requested=model, success=True,
            model_used=model, latency_ms=latency_ms, finish_reason=raw["finish_reason"],
            input_tokens=raw["usage"].get("prompt_tokens"),
            output_tokens=raw["usage"].get("completion_tokens"),
            user_id=user_id,
        )
        return GatewayResult(
            content=final_content,
            model_used=raw["model"],
            attempts=attempts,
            latency_ms=latency_ms,
            finish_reason=raw["finish_reason"],
            input_tokens=raw["usage"].get("prompt_tokens"),
            output_tokens=raw["usage"].get("completion_tokens"),
        )

    raise AIGatewayError(
        f"Semua {len(attempts)} model AI gagal dipanggil. Error terakhir: {last_error}"
    )


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------
async def stream_text(
    *,
    messages: list[dict[str, str]],
    endpoint_type: str = "chat",
    user_id: uuid.UUID | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
):
    """Versi streaming dari generate_text.

    Yield tuple (kind, payload):
      ("model",  {"model": str})                    — token pertama berhasil
      ("delta",  {"text": str})                     — potongan jawaban
      ("crisis", {"attempts": [...]})               — output terindikasi krisis
                                                      (partial dibuang pemanggil)
      ("done",   {"model_used","latency_ms","attempts","input_tokens",
                  "output_tokens","finish_reason"})
      ("error",  {"detail": str})                   — gagal total / terputus

    Fallback antar model HANYA sebelum token pertama keluar.
    Raise CrisisDetectedError / OffTopicDetectedError utk INPUT krisis/offtopik
    (sebelum stream dibuka).
    """
    crisis = detect_crisis(_last_user_text(messages))
    if crisis.flagged:
        await _log_attempt(
            endpoint_type=endpoint_type,
            model_requested=settings.AI_MODEL_DEFAULT,
            success=False,
            error_type="crisis_input_detected",
            error_detail=f"keyword={crisis.matched_keyword!r}",
            user_id=user_id,
        )
        raise CrisisDetectedError(source="input", matched_keyword=crisis.matched_keyword)

    if endpoint_type == "chat":
        offtopic = detect_offtopic(_last_user_text(messages))
        if offtopic.flagged:
            await _log_attempt(
                endpoint_type=endpoint_type,
                model_requested=settings.AI_MODEL_DEFAULT,
                success=False,
                error_type="offtopic_input_detected",
                error_detail=f"pattern={offtopic.matched_pattern!r}",
                user_id=user_id,
            )
            raise OffTopicDetectedError(matched_pattern=offtopic.matched_pattern)

    client = get_openrouter_client()
    attempts: list[AttemptInfo] = []

    for model in settings.ai_model_candidates:
        started = time.perf_counter()
        emitted = False
        parts: list[str] = []
        usage: dict = {}
        finish_reason: str | None = None

        try:
            resp = await client.stream_open(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except OpenRouterAuthError as exc:
            attempts.append(AttemptInfo(model=model, ok=False, error=str(exc)))
            await _log_attempt(
                endpoint_type=endpoint_type, model_requested=model, success=False,
                error_type="auth_error", error_detail=str(exc), user_id=user_id,
            )
            raise AIConfigurationError(str(exc)) from exc
        except OpenRouterRateLimitError as exc:
            attempts.append(AttemptInfo(model=model, ok=False, error=str(exc)[:300]))
            await _log_attempt(
                endpoint_type=endpoint_type, model_requested=model, success=False,
                error_type="rate_limit", error_detail=str(exc)[:500], user_id=user_id,
            )
            continue
        except OpenRouterError as exc:  # timeout/provider saat membuka stream
            attempts.append(AttemptInfo(model=model, ok=False, error=str(exc)[:300]))
            error_kind = "timeout" if isinstance(exc, OpenRouterTimeoutError) else "provider_error"
            await _log_attempt(
                endpoint_type=endpoint_type, model_requested=model, success=False,
                error_type=error_kind, error_detail=str(exc)[:500], user_id=user_id,
            )
            continue

        try:
            async for piece, chunk_usage, chunk_finish, err in client.iter_sse_deltas(resp):
                if err:
                    raise OpenRouterProviderError(str(err.get("message") or err)[:300])
                if chunk_usage:
                    usage = chunk_usage
                if chunk_finish:
                    finish_reason = chunk_finish
                if piece:
                    if not emitted:
                        emitted = True
                        yield ("model", {"model": model})
                    parts.append(piece)
                    # Crisis scan inkremental pada jendela teks terakhir
                    tail = "".join(parts[-6:])[-200:]
                    out_hit = detect_crisis(tail)
                    if out_hit.flagged:
                        attempts.append(AttemptInfo(model=model, ok=True))
                        await _log_attempt(
                            endpoint_type=endpoint_type, model_requested=model, success=False,
                            model_used=model, finish_reason=finish_reason,
                            input_tokens=usage.get("prompt_tokens"),
                            output_tokens=usage.get("completion_tokens"),
                            error_type="crisis_output_detected",
                            error_detail=f"keyword={out_hit.matched_keyword!r}",
                            user_id=user_id,
                        )
                        yield (
                            "crisis",
                            {
                                "attempts": [
                                    {"model": a.model, "ok": a.ok, "error": a.error}
                                    for a in attempts
                                ]
                            },
                        )
                        return
                    yield ("delta", {"text": piece})
        except OpenRouterProviderError as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            attempts.append(AttemptInfo(model=model, ok=False, error=str(exc)[:300]))
            await _log_attempt(
                endpoint_type=endpoint_type, model_requested=model, success=False,
                error_type="provider_error", error_detail=str(exc)[:500],
                latency_ms=latency_ms, user_id=user_id,
            )
            if emitted:
                yield ("error", {"detail": "Koneksi ke AI terputus di tengah jawaban."})
                return
            continue  # belum ada yang keluar -> fallback model berikutnya

        latency_ms = int((time.perf_counter() - started) * 1000)

        if not emitted:
            # Stream sukses tapi tanpa konten — perlakukan sebagai provider error
            attempts.append(AttemptInfo(model=model, ok=False, error="konten kosong"))
            await _log_attempt(
                endpoint_type=endpoint_type, model_requested=model, success=False,
                error_type="provider_error", error_detail="stream kosong",
                latency_ms=latency_ms, user_id=user_id,
            )
            continue

        attempts.append(AttemptInfo(model=model, ok=True))
        await _log_attempt(
            endpoint_type=endpoint_type, model_requested=model, success=True,
            model_used=model, latency_ms=latency_ms, finish_reason=finish_reason,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            user_id=user_id,
        )
        yield (
            "done",
            {
                "model_used": model,
                "latency_ms": latency_ms,
                "attempts": [{"model": a.model, "ok": a.ok, "error": a.error} for a in attempts],
                "input_tokens": usage.get("prompt_tokens"),
                "output_tokens": usage.get("completion_tokens"),
                "finish_reason": finish_reason,
            },
        )
        return

    yield ("error", {"detail": f"Semua {len(attempts)} model AI gagal dipanggil."})

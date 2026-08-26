"""Wrapper async ke OpenRouter API (protokol OpenAI-compatible).

Satu API key -> akses banyak provider/model. Dokumentasi:
https://openrouter.ai/docs

Error DITIPEKAN agar router.py bisa memutuskan fallback vs fail-fast:
- AuthError (401/402)   : key invalid/kredit habis -> JANGAN fallback (key sama utk semua model)
- RateLimitError (429)  : fallback ke model berikutnya
- ProviderError (5xx, konten kosong, jaringan) : fallback ke model berikutnya
"""

import json

import httpx

from app.core.config import settings


class OpenRouterError(Exception):
    """Dasar semua error dari lapisan OpenRouter client."""


class OpenRouterAuthError(OpenRouterError):
    """API key tidak valid atau kredit habis — fail-fast, fallback percuma."""


class OpenRouterRateLimitError(OpenRouterError):
    """HTTP 429 — layak dicoba model berikutnya."""


class OpenRouterProviderError(OpenRouterError):
    """Error upstream lain / respons tidak valid — layak dicoba model berikutnya."""


class OpenRouterTimeoutError(OpenRouterProviderError):
    """Timeout koneksi atau baca respons."""


class OpenRouterClient:
    """Satu instance shared (connection pooling) — akses via get_openrouter_client()."""

    def __init__(
        self,
        api_key: str | None,
        base_url: str,
        timeout_seconds: float,
        disable_reasoning: bool = True,
    ) -> None:
        if not api_key:
            raise OpenRouterAuthError(
                "OPENROUTER_API_KEY belum diset di .env — gateway tidak bisa jalan"
            )
        self._disable_reasoning = disable_reasoning
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {api_key}",
                # Header atribusi aplikasi OpenRouter (opsional tapi direkomendasikan)
                "HTTP-Referer": "http://localhost:5173",
                "X-Title": "Ruang Kita",
            },
            timeout=httpx.Timeout(
                connect=10.0, read=timeout_seconds, write=30.0, pool=10.0
            ),
        )

    @property
    def is_closed(self) -> bool:
        return self._http.is_closed

    async def aclose(self) -> None:
        await self._http.aclose()

    async def chat_completion(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        """Panggil /chat/completions.

        Return dict ternormalisasi:
            {"content": str, "model": str, "finish_reason": str|None,
             "usage": {"prompt_tokens": int|None, "completion_tokens": int|None}}
        Raise OpenRouter*Error sesuai kategori di atas.
        """
        payload = self._build_payload(
            model=model, messages=messages,
            temperature=temperature, max_tokens=max_tokens,
        )

        try:
            resp = await self._http.post("/chat/completions", json=payload)
        except httpx.TimeoutException as exc:
            raise OpenRouterTimeoutError(f"Timeout memanggil {model}: {exc}") from exc
        except httpx.HTTPError as exc:
            raise OpenRouterProviderError(f"Jaringan gagal memanggil {model}: {exc}") from exc

        body = self._safe_json(resp, model)
        if resp.status_code != 200:
            self._raise_for_status(body, resp.status_code)

        choices = body.get("choices") or []
        message = (choices[0].get("message") or {}) if choices else {}
        content = message.get("content")
        if not content or not str(content).strip():
            # Beberapa model reasoning mengembalikan content null/kosong
            raise OpenRouterProviderError(f"{model} mengembalikan konten kosong")

        usage = body.get("usage") or {}
        return {
            "content": content,
            "model": body.get("model") or model,
            "finish_reason": choices[0].get("finish_reason"),
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
            },
        }

    def _build_payload(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float | None,
        max_tokens: int | None,
        stream: bool = False,
    ) -> dict:
        payload: dict = {"model": model, "messages": messages}
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if stream:
            payload["stream"] = True
            # Minta usage dikirim di chunk terakhir (ekstensi OpenRouter)
            payload["usage"] = {"include": True}
        if self._disable_reasoning:
            # Cegah reasoning-model memunculkan proses berpikir ke konten jawaban.
            # require_parameters: hanya route ke provider yang menghormati param ini.
            payload["reasoning"] = {"enabled": False}
            payload["provider"] = {"require_parameters": True}
        return payload

    @staticmethod
    def _raise_for_status(body: dict, status_code: int) -> None:
        err = body.get("error") or {}
        msg = err.get("message") or f"HTTP {status_code} tanpa detail"
        raw = (err.get("metadata") or {}).get("raw")
        msg = msg + (f" ({raw})" if raw else "")
        if status_code in (401, 402):
            raise OpenRouterAuthError(msg)
        if status_code == 429:
            raise OpenRouterRateLimitError(msg)
        raise OpenRouterProviderError(msg)

    # ------------------------------------------------------------------
    # Streaming (SSE)
    # ------------------------------------------------------------------
    async def stream_open(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> httpx.Response:
        """Buka stream SSE. Return response mentah — ditutup otomatis oleh
        iter_sse_deltas(). Error sebelum token pertama -> typed error (fallback-able).
        """
        payload = self._build_payload(
            model=model, messages=messages,
            temperature=temperature, max_tokens=max_tokens, stream=True,
        )
        try:
            request = self._http.build_request("POST", "/chat/completions", json=payload)
            resp = await self._http.send(request, stream=True)
        except httpx.TimeoutException as exc:
            raise OpenRouterTimeoutError(f"Timeout membuka stream {model}: {exc}") from exc
        except httpx.HTTPError as exc:
            raise OpenRouterProviderError(f"Jaringan gagal membuka stream {model}: {exc}") from exc

        if resp.status_code != 200:
            body: dict = {}
            try:
                body = self._safe_json(resp, model)
            except OpenRouterProviderError:
                pass  # body bukan JSON — tetap lempar error status
            await resp.aclose()
            self._raise_for_status(body, resp.status_code)
        return resp

    async def iter_sse_deltas(self, resp: httpx.Response):
        """Parse SSE OpenAI-compatible. Yield tuple (piece, usage, finish_reason, error).

        Menutup resp otomatis saat generator selesai/di-break pemanggil.
        """
        try:
            async for line in resp.aiter_lines():
                line = line.strip()
                if not line or line.startswith(":"):
                    continue  # keep-alive comment OpenRouter ("OPENROUTER PROCESSING")
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except ValueError:
                    continue
                if not isinstance(obj, dict):
                    continue
                if obj.get("error"):
                    yield None, None, None, obj["error"]
                    break
                choices = obj.get("choices") or []
                delta = (choices[0].get("delta") or {}) if choices else {}
                piece = delta.get("content")
                usage = obj.get("usage")
                finish = choices[0].get("finish_reason") if choices else None
                if piece or usage or finish:
                    yield piece, usage, finish, None
        finally:
            await resp.aclose()

    @staticmethod
    def _safe_json(resp: httpx.Response, model: str) -> dict:
        try:
            return resp.json()
        except ValueError as exc:
            raise OpenRouterProviderError(
                f"{model}: respons bukan JSON (HTTP {resp.status_code})"
            ) from exc

    @staticmethod
    def _error_message(body: dict, status_code: int) -> str:
        err = body.get("error") or {}
        msg = err.get("message") or f"HTTP {status_code} tanpa detail"
        raw = (err.get("metadata") or {}).get("raw")
        return f"{msg}" + (f" ({raw})" if raw else "")


_client: OpenRouterClient | None = None


def get_openrouter_client() -> OpenRouterClient:
    """Lazy singleton — dibuat saat pertama dipanggil, ditutup di app lifespan."""
    global _client
    if _client is None or _client.is_closed:
        _client = OpenRouterClient(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL,
            timeout_seconds=settings.AI_TIMEOUT_SECONDS,
            disable_reasoning=settings.AI_DISABLE_REASONING,
        )
    return _client


async def close_openrouter_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None

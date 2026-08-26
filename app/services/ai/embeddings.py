"""Embedding provider (Gemini REST) untuk RAG semantik — Fase 2.

Desain:
- Tanpa SDK tambahan: httpx langsung ke endpoint embedContent.
- Graceful degradation: tanpa GEMINI_API_KEY / saat error -> embed_text() return None,
  retrieval otomatis jatuh kembali ke leksikal. TIDAK PERNAH melempar exception ke pemanggil.
- Client httpx dipakai bersama (pola sama dengan openrouter_client) dan ditutup di lifespan.
"""

import logging
import math
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

logger = logging.getLogger(__name__)

_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
_MAX_EMBED_CHARS = 2000  # hemat kuota; snippet grounding juga hanya ±600 char

_client: httpx.AsyncClient | None = None


def get_embed_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=15.0)
    return _client


async def close_embed_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


def is_enabled() -> bool:
    """Semantik aktif hanya bila flag on + API key terisi."""
    return bool(settings.RAG_SEMANTIC_ENABLED and settings.GEMINI_API_KEY)


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


async def embed_text(text: str) -> list[float] | None:
    """Embed teks via Gemini. Return None bila disabled/gagal — TANPA raise."""
    if not text or not text.strip() or not is_enabled():
        return None
    try:
        resp = await get_embed_client().post(
            f"{_GEMINI_BASE}/models/{settings.EMBEDDING_MODEL}:embedContent",
            params={"key": settings.GEMINI_API_KEY},
            json={
                "model": f"models/{settings.EMBEDDING_MODEL}",
                "content": {"parts": [{"text": text[:_MAX_EMBED_CHARS]}]},
            },
        )
        resp.raise_for_status()
        values = resp.json().get("embedding", {}).get("values")
        return values if isinstance(values, list) and values else None
    except Exception:  # noqa: BLE001 — semantik bersifat best-effort
        logger.warning("embed_text gagal (fallback leksikal)", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Teks sumber per entitas + penyimpanan vektor
# ---------------------------------------------------------------------------


def topic_source_text(t) -> str:
    parts = [t.name, t.summary]
    if t.alt_names:
        parts.append("Istilah lain: " + ", ".join(t.alt_names))
    if t.signs_symptoms:
        parts.append("Tanda: " + "; ".join(t.signs_symptoms[:5]))
    parts.append(f"Kategori: {t.category}")
    return "\n".join(p for p in parts if p)


def content_source_text(c) -> str:
    parts = [c.title]
    if c.summary:
        parts.append(c.summary)
    if c.content_body:
        parts.append(c.content_body[:500])
    if c.topics:
        parts.append("Tag: " + ", ".join(c.topics))
    return "\n".join(p for p in parts if p)


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def embed_and_store_topic(db: AsyncSession, topic) -> bool:
    """Embed & simpan vektor satu topik. Return True bila vektor tersimpan."""
    try:
        vec = await embed_text(topic_source_text(topic))
        if vec is None:
            return False
        topic.embedding = vec
        topic.embedded_at = _utcnow()
        await db.commit()
        return True
    except Exception:  # noqa: BLE001
        logger.warning("Gagal menyimpan embedding topik %s", getattr(topic, "slug", "?"), exc_info=True)
        return False


async def embed_and_store_content(db: AsyncSession, item) -> bool:
    try:
        vec = await embed_text(content_source_text(item))
        if vec is None:
            return False
        item.embedding = vec
        item.embedded_at = _utcnow()
        await db.commit()
        return True
    except Exception:  # noqa: BLE001
        logger.warning("Gagal menyimpan embedding konten %s", getattr(item, "slug", "?"), exc_info=True)
        return False

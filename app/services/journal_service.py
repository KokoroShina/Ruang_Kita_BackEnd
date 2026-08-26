"""Service fitur Kenali — analisis jurnal one-shot via AI Gateway.

Alur analyze_entry():
1. Crisis pre-check konten jurnal -> flagged? simpan flag + insight dukungan (tanpa AI).
2. Normal -> gateway (fallback internal) -> ai_insight terisi (sudah ber-disclaimer).
3. Crisis output -> insight diganti pesan dukungan + flag.
Entri jurnal TIDAK PERNAH hilang walau AI gagal.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.journal_entry import JournalEntry
from app.services.ai.guardrails import SUPPORT_REDIRECT_TEXT, detect_crisis
from app.services.ai.prompts.journal_prompt import build_journal_messages
from app.services.ai.router import (
    AIGatewayError,
    AttemptInfo,
    CrisisDetectedError,
    generate_text,
)


class JournalEntryNotFoundError(Exception):
    """Entri tidak ada ATAU milik user lain — sama-sama 404."""


@dataclass(slots=True)
class AnalyzeResult:
    entry: JournalEntry
    crisis_detected: bool = False
    model_used: str | None = None
    latency_ms: int | None = None
    attempts: list[AttemptInfo] = field(default_factory=list)
    grounded_topics: list[str] = field(default_factory=list)


async def _owned_entry(
    db: AsyncSession, *, user_id: uuid.UUID, entry_id: uuid.UUID
) -> JournalEntry:
    result = await db.execute(
        select(JournalEntry).where(
            JournalEntry.id == entry_id, JournalEntry.user_id == user_id
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise JournalEntryNotFoundError()
    return entry


async def create_entry(
    db: AsyncSession, *, user_id: uuid.UUID, content: str, title: str | None = None
) -> JournalEntry:
    entry = JournalEntry(user_id=user_id, title=title, content=content)
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def list_entries(
    db: AsyncSession, *, user_id: uuid.UUID, limit: int = 50, offset: int = 0
) -> list[JournalEntry]:
    result = await db.execute(
        select(JournalEntry)
        .where(JournalEntry.user_id == user_id)
        .order_by(JournalEntry.created_at.desc())
        .limit(min(limit, 100))
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_entry(db: AsyncSession, *, user_id: uuid.UUID, entry_id: uuid.UUID) -> JournalEntry:
    return await _owned_entry(db, user_id=user_id, entry_id=entry_id)


async def delete_entry(db: AsyncSession, *, user_id: uuid.UUID, entry_id: uuid.UUID) -> None:
    """Hard delete — pilar privasi."""
    entry = await _owned_entry(db, user_id=user_id, entry_id=entry_id)
    await db.delete(entry)
    await db.commit()


async def update_entry(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    entry_id: uuid.UUID,
    title: str | None = None,
    content: str | None = None,
) -> JournalEntry:
    """Update sebagian field. Jika konten berubah, insight lama dibuang (stale)."""
    entry = await _owned_entry(db, user_id=user_id, entry_id=entry_id)
    if title is not None:
        entry.title = title
    if content is not None and content != entry.content:
        entry.content = content
        entry.ai_insight = None  # insight lama tidak lagi relevan
    await db.commit()
    await db.refresh(entry)
    return entry


async def analyze_entry(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    entry_id: uuid.UUID,
    temperature: float | None = None,
    max_tokens: int | None = 600,
) -> AnalyzeResult:
    """Analisis satu entri jurnal -> ai_insight. Bisa dipanggil ulang (overwrite)."""
    entry = await _owned_entry(db, user_id=user_id, entry_id=entry_id)

    # ---- Crisis INPUT --------------------------------------------------------
    input_crisis = detect_crisis(entry.content)
    if input_crisis.flagged:
        entry.crisis_flagged = True
        entry.ai_insight = SUPPORT_REDIRECT_TEXT
        await db.commit()
        await db.refresh(entry)
        return AnalyzeResult(entry=entry, crisis_detected=True)

    # ---- RAG: grounding konten psikoedukasi bila topik disebut ----------------
    from app.services.ai.retriever import retrieve_context  # import lokal (hindari siklus)

    retrieval = await retrieve_context(db, entry.content)

    # ---- Gateway --------------------------------------------------------------
    try:
        result = await generate_text(
            messages=build_journal_messages(
                entry.content, context_snippets=retrieval.snippets or None
            ),
            endpoint_type="journal_analysis",
            user_id=user_id,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except CrisisDetectedError as exc:
        # Output AI terindikasi krisis (jarang) — ganti dengan pesan dukungan
        entry.crisis_flagged = exc.source == "output"
        entry.ai_insight = SUPPORT_REDIRECT_TEXT
        await db.commit()
        await db.refresh(entry)
        return AnalyzeResult(entry=entry, crisis_detected=True)

    entry.ai_insight = result.content
    await db.commit()
    await db.refresh(entry)
    return AnalyzeResult(
        entry=entry,
        crisis_detected=False,
        model_used=result.model_used,
        latency_ms=result.latency_ms,
        attempts=result.attempts,
        grounded_topics=retrieval.topic_slugs,
    )


__all__ = [
    "AnalyzeResult",
    "JournalEntryNotFoundError",
    "analyze_entry",
    "create_entry",
    "delete_entry",
    "get_entry",
    "list_entries",
    "update_entry",
]

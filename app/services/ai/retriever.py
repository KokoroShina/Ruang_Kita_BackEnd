"""Retrieval untuk RAG — grounding konten psikoedukasi ke LLM.

Fase 1 (leksikal): cocokkan penyebutan eksplisit topik (name/slug/alt_names)
dan konten library pada teks user. Deterministik, tanpa biaya.

Fase 2 (semantik): bila GEMINI_API_KEY terisi, query di-embed lalu dibandingkan
cosine vs vektor topik published — menangkap parafrase tanpa kata kunci persis.
Kegagalan embedding / tanpa key -> otomatis jatuh ke leksikal (graceful).

Antarmuka retrieve_context() stabil untuk kedua fase. Draft TIDAK PERNAH diambil.
Jalur crisis TIDAK memanggil retriever — safety selalu langkah pertama.
"""

import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_library import ContentLibrary
from app.models.mental_health_topic import MentalHealthTopic

logger = logging.getLogger(__name__)

MAX_SNIPPET_CHARS = 600
DEFAULT_MAX_TOPICS = 2
DEFAULT_MAX_CONTENT = 2


@dataclass(slots=True)
class RetrievalResult:
    snippets: list[str] = field(default_factory=list)      # blok teks utk context_snippets
    topic_slugs: list[str] = field(default_factory=list)   # utk field grounded_topics
    content_slugs: list[str] = field(default_factory=list)

    @property
    def has_context(self) -> bool:
        return bool(self.snippets)


def _needles_for_topic(topic: MentalHealthTopic) -> list[str]:
    candidates = [topic.name.lower(), topic.slug.lower()]
    candidates.extend((a or "").lower() for a in (topic.alt_names or []))
    seen: set[str] = set()
    needles: list[str] = []
    for c in candidates:
        if len(c) >= 3 and c not in seen:  # abaikan terlalu pendek (noise)
            seen.add(c)
            needles.append(c)
    return needles


def _truncate(text: str, limit: int = MAX_SNIPPET_CHARS) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _topic_snippet(t: MentalHealthTopic) -> str:
    parts = [f"[Topik: {t.name}]"]
    parts.append(f"Ringkasan: {t.summary}")
    if t.signs_symptoms:
        parts.append("Tanda umum: " + "; ".join(t.signs_symptoms[:3]))
    if t.when_to_seek_help:
        parts.append(f"Kapan mencari bantuan: {t.when_to_seek_help}")
    parts.append(f"Halaman bacaan user: /topics/{t.slug}")
    return _truncate("\n".join(parts))


def _content_snippet(c: ContentLibrary) -> str:
    dur = f", ±{c.duration_minutes} menit" if c.duration_minutes else ""
    parts = [f"[Konten: {c.title} ({c.content_type}{dur})]"]
    if c.summary:
        parts.append(f"Ringkasan: {c.summary}")
    parts.append(f"Halaman bacaan user: /content/{c.slug}")
    return _truncate("\n".join(parts))


async def retrieve_context(
    db: AsyncSession,
    text: str,
    *,
    max_topics: int = DEFAULT_MAX_TOPICS,
    max_content: int = DEFAULT_MAX_CONTENT,
) -> RetrievalResult:
    """Cari topik/konten published yang DISIBUT eksplisit dalam teks.

    Return RetrievalResult; snippets kosong bila tidak ada kecocokan —
    pemanggil tinggal melewatkan None ke build_*_messages.
    """
    result = RetrievalResult()
    lowered = (text or "").lower()
    if not lowered.strip():
        return result

    topics = (
        await db.execute(
            select(MentalHealthTopic).where(MentalHealthTopic.is_published.is_(True))
        )
    ).scalars().all()

    matched_topics: list[MentalHealthTopic] = []
    for t in topics:
        if any(needle in lowered for needle in _needles_for_topic(t)):
            matched_topics.append(t)
            if len(matched_topics) >= max_topics:
                break

    for t in matched_topics:
        result.snippets.append(_topic_snippet(t))
        result.topic_slugs.append(t.slug)

    # Konten di-grounding hanya jika SANGAT spesifik: slug-nya disebut,
    # atau tag-nya persis slug topik yang baru saja cocok (bukan sekadar kategori).
    matched_slugs = {t.slug for t in matched_topics}
    contents = (
        await db.execute(
            select(ContentLibrary).where(ContentLibrary.is_published.is_(True))
        )
    ).scalars().all()

    for c in contents:
        tags = {(x or "").lower() for x in (c.topics or [])}
        title_hit = len(c.title) >= 4 and c.title.lower() in lowered
        if c.slug in lowered or title_hit or (tags & matched_slugs):
            result.snippets.append(_content_snippet(c))
            result.content_slugs.append(c.slug)
            if len(result.content_slugs) >= max_content:
                break

    # ---- Fase 2: semantic pass (parafrase tanpa kata kunci persis) -------------
    if len(result.topic_slugs) < max_topics:
        await _semantic_pass(db, text, result, exclude=matched_slugs, max_topics=max_topics)

    return result


async def _semantic_pass(
    db: AsyncSession,
    text: str,
    result: RetrievalResult,
    *,
    exclude: set[str],
    max_topics: int,
) -> None:
    """Tambah topik via cosine similarity. Best-effort — gagal = diam-diam leksikal saja."""
    try:
        from app.core.config import settings
        from app.services.ai import embeddings as emb

        if not emb.is_enabled():
            return

        query_vec = await emb.embed_text(text)
        if not query_vec:
            return

        rows = (
            await db.execute(
                select(MentalHealthTopic).where(
                    MentalHealthTopic.is_published.is_(True),
                    MentalHealthTopic.embedding.is_not(None),
                )
            )
        ).scalars().all()

        scored = []
        for t in rows:
            if t.slug in exclude or len(t.embedding) != len(query_vec):
                continue
            score = emb.cosine(query_vec, t.embedding)
            if score >= settings.EMBEDDING_SIMILARITY_THRESHOLD:
                scored.append((score, t))
        scored.sort(key=lambda pair: -pair[0])

        for score, t in scored:
            if len(result.topic_slugs) >= max_topics:
                break
            result.snippets.append(_topic_snippet(t))
            result.topic_slugs.append(t.slug)
            logger.info("RAG semantic match %s (cos=%.3f)", t.slug, score)
    except Exception:  # noqa: BLE001 — semantik best-effort, jangan ganggu jawaban
        logger.warning("Semantic pass gagal (lanjut leksikal)", exc_info=True)

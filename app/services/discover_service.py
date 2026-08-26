"""Service Temukan v1 — rekomendasi rule-based (pra-RAG) + browse content library.

Sinyal yang dipakai (semua lokal, tanpa AI):
1. Penyebutan topik di jurnal terbaru (nama/slug/alt_names)  -> skor tertinggi
2. Label mood terakhir (mapping kata -> kategori)            -> skor menengah
3. Tren mood rendah (avg < 3 pada 14 hari)                   -> konten coping
4. Fallback umum: konten wellbeing populer                   -> bila sinyal minim
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_library import ContentLibrary
from app.models.journal_entry import JournalEntry
from app.models.mental_health_topic import MentalHealthTopic
from app.models.mood_log import MoodLog

# Mapping kata label mood (substring, lowercase) -> kategori topik
MOOD_LABEL_HINTS: tuple[tuple[str, str], ...] = (
    ("cemas", "anxiety"),
    ("panik", "anxiety"),
    ("takut", "anxiety"),
    ("khawatir", "anxiety"),
    ("sedih", "mood"),
    ("murung", "mood"),
    ("down", "mood"),
    ("putus asa", "mood"),
    ("capek", "burnout"),
    ("lelah", "burnout"),
    ("burnout", "burnout"),
    ("boreout", "burnout"),
    ("trauma", "trauma"),
    ("makan", "eating"),
)

LOW_MOOD_THRESHOLD = 3.0
JOURNAL_LOOKBACK_DAYS = 30
MOOD_LOOKBACK_DAYS = 14
TOPIC_SCORE_JOURNAL = 5
TOPIC_SCORE_LABEL = 3
TOPIC_SCORE_LOW_MOOD_CATEGORY = 2


class ContentSlugExistsError(Exception):
    pass


class ContentNotFoundError(Exception):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ===== Content library =====


async def list_content(
    db: AsyncSession,
    *,
    include_unpublished: bool = False,
    content_type: str | None = None,
    topic: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ContentLibrary]:
    stmt = select(ContentLibrary).order_by(ContentLibrary.title.asc())
    if not include_unpublished:
        stmt = stmt.where(ContentLibrary.is_published.is_(True))
    if content_type:
        stmt = stmt.where(ContentLibrary.content_type == content_type.strip().lower())
    if topic:
        pattern = f'%"{topic.strip().lower()}"%'
        stmt = stmt.where(func.cast(ContentLibrary.topics, __import__("sqlalchemy").Text).ilike(pattern))
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                ContentLibrary.title.ilike(pattern),
                ContentLibrary.slug.ilike(pattern),
                func.cast(ContentLibrary.summary, __import__("sqlalchemy").Text).ilike(pattern),
            )
        )
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_content(db: AsyncSession, *, data: dict) -> ContentLibrary:
    slug = data["slug"].strip().lower()
    existing = await db.scalar(
        select(func.count()).select_from(ContentLibrary).where(ContentLibrary.slug == slug)
    )
    if existing:
        raise ContentSlugExistsError
    item = ContentLibrary(slug=slug, **{k: v for k, v in data.items() if k != "slug"})
    if item.is_published and item.published_at is None:
        item.published_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(item)
    await db.commit()
    await db.refresh(item)

    if item.is_published:
        from app.services.ai import embeddings as emb

        await emb.embed_and_store_content(db, item)
        await db.refresh(item)
    return item


async def update_content(db: AsyncSession, *, slug: str, changes: dict) -> ContentLibrary:
    item = (
        await db.execute(select(ContentLibrary).where(ContentLibrary.slug == slug.strip().lower()))
    ).scalar_one_or_none()
    if item is None:
        raise ContentNotFoundError
    was_published = item.is_published
    for field, value in changes.items():
        setattr(item, field, value)
    if not was_published and item.is_published and item.published_at is None:
        item.published_at = datetime.now(timezone.utc).replace(tzinfo=None)
    if was_published and not item.is_published:
        item.published_at = None
    await db.commit()
    await db.refresh(item)

    if item.is_published:
        from app.services.ai import embeddings as emb

        await emb.embed_and_store_content(db, item)
        await db.refresh(item)
    return item


async def delete_content(db: AsyncSession, *, slug: str) -> None:
    item = (
        await db.execute(select(ContentLibrary).where(ContentLibrary.slug == slug.strip().lower()))
    ).scalar_one_or_none()
    if item is None:
        raise ContentNotFoundError
    await db.delete(item)
    await db.commit()


# ===== Rekomendasi rule-based =====


def _text_haystack(topic: MentalHealthTopic) -> list[str]:
    needles = [topic.name.lower(), topic.slug.lower(), *(a.lower() for a in (topic.alt_names or []))]
    return [n for n in needles if len(n) >= 3]


async def build_recommendations(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    max_topics: int = 3,
    max_content: int = 4,
) -> dict:
    now = _utcnow()
    based_on: list[str] = []

    # --- Sinyal 1: penyebutan topik di jurnal terbaru ---
    journal_cutoff = now - timedelta(days=JOURNAL_LOOKBACK_DAYS)
    journals = (
        await db.execute(
            select(JournalEntry.title, JournalEntry.content)
            .where(JournalEntry.user_id == user_id, JournalEntry.created_at >= journal_cutoff)
            .order_by(JournalEntry.created_at.desc())
            .limit(20)
        )
    ).all()
    journal_text = "\n".join(f"{t or ''} {c}" for t, c in journals).lower()

    published_topics = (
        await db.execute(select(MentalHealthTopic).where(MentalHealthTopic.is_published.is_(True)))
    ).scalars().all()

    topic_scores: dict[str, int] = {}
    topic_reasons: dict[str, list[dict]] = {}

    def add_score(slug: str, points: int, reason: dict) -> None:
        topic_scores[slug] = topic_scores.get(slug, 0) + points
        topic_reasons.setdefault(slug, []).append(reason)

    matched_by_journal: set[str] = set()
    for topic in published_topics:
        for needle in _text_haystack(topic):
            if needle in journal_text:
                matched_by_journal.add(topic.slug)
                add_score(
                    topic.slug,
                    TOPIC_SCORE_JOURNAL,
                    {
                        "kind": "journal_topic_match",
                        "detail": f"kamu menyinggung '{needle}' di jurnal terbaru",
                    },
                )
                break

    # --- Sinyal 2: label mood terakhir (14 hari) ---
    mood_cutoff = now - timedelta(days=MOOD_LOOKBACK_DAYS)
    moods = (
        await db.execute(
            select(MoodLog.mood_score, MoodLog.mood_label)
            .where(MoodLog.user_id == user_id, MoodLog.logged_at >= mood_cutoff)
            .order_by(MoodLog.logged_at.desc())
        )
    ).all()

    hinted_categories: list[str] = []
    seen_labels: list[str] = []
    for score, label in moods:
        if not label:
            continue
        low = label.lower()
        if any(low in seen for seen in seen_labels):
            continue
        seen_labels.append(low)
        for keyword, category in MOOD_LABEL_HINTS:
            if keyword in low and category not in hinted_categories:
                hinted_categories.append(category)
                based_on.append(f"mood-mu terasa '{label}'")
                break

    for topic in published_topics:
        if topic.slug in matched_by_journal:
            continue
        if topic.category in hinted_categories:
            add_score(
                topic.slug,
                TOPIC_SCORE_LABEL,
                {
                    "kind": "mood_label",
                    "detail": f"relevan dengan mood-mu belakangan ({topic.category})",
                },
            )

    # --- Sinyal 3: tren mood rendah -> konten coping ---
    scores_recent = [s for s, _ in moods if s is not None]
    low_mood_trend = bool(scores_recent) and (sum(scores_recent) / len(scores_recent)) < LOW_MOOD_THRESHOLD
    if low_mood_trend:
        based_on.append("mood-mu cenderung rendah dua minggu terakhir")
        for topic in published_topics:
            if topic.category == "mood":
                add_score(
                    topic.slug,
                    TOPIC_SCORE_LOW_MOOD_CATEGORY,
                    {"kind": "low_mood_trend", "detail": "mendukungmu saat mood sedang rendah"},
                )

    # --- Susun hasil topik ---
    ranked = sorted(topic_scores.items(), key=lambda kv: (-kv[1], kv[0]))[:max_topics]
    by_slug = {t.slug: t for t in published_topics}
    topics_out = [
        {
            "slug": slug,
            "name": by_slug[slug].name,
            "category": by_slug[slug].category,
            "summary": by_slug[slug].summary,
            "score": score,
            "reasons": topic_reasons.get(slug, []),
        }
        for slug, score in ranked
    ]

    # --- Konten: match topics/kategori dari rekomendasi + fallback wellbeing ---
    target_topic_slugs = {slug for slug, _ in ranked}
    target_categories = {by_slug[slug].category.lower() for slug, _ in ranked}
    content_items = (
        await db.execute(
            select(ContentLibrary)
            .where(ContentLibrary.is_published.is_(True))
            .order_by(ContentLibrary.title.asc())
        )
    ).scalars().all()

    content_out = []
    fallback_pool: list[ContentLibrary] = []
    for item in content_items:
        item_topics = {(t or "").lower() for t in (item.topics or [])}
        slug_overlap = sorted(target_topic_slugs & item_topics)
        category_overlap = sorted(item_topics & target_categories)
        if slug_overlap or category_overlap:
            content_out.append(
                {
                    "slug": item.slug,
                    "title": item.title,
                    "content_type": item.content_type,
                    "summary": item.summary,
                    "duration_minutes": item.duration_minutes,
                    "matched_topics": slug_overlap or category_overlap,
                }
            )
        else:
            fallback_pool.append(item)

    if not content_out and fallback_pool:
        for item in fallback_pool[:max_content]:
            content_out.append(
                {
                    "slug": item.slug,
                    "title": item.title,
                    "content_type": item.content_type,
                    "summary": item.summary,
                    "duration_minutes": item.duration_minutes,
                    "matched_topics": [],
                }
            )
        based_on.append("pilihan umum untuk merawat diri")
    content_out = content_out[:max_content]

    if journals:
        based_on.append(f"{len(journals)} entri jurnal terakhirmu")
    if not based_on:
        based_on.append("belum ada sinyal personal — ini pilihan umum")

    return {
        "based_on": based_on[:4],
        "topics": topics_out,
        "content": content_out,
    }

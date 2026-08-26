"""Service ensiklopedia kesehatan mental — baca publik, kelola admin."""

from datetime import datetime, timezone

from sqlalchemy import func, or_, select, Text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mental_health_topic import MentalHealthTopic
from app.models.user import User


class TopicSlugExistsError(Exception):
    pass


class TopicNotFoundError(Exception):
    pass


def _normalize_slug(slug: str) -> str:
    return slug.strip().lower()


async def list_topics(
    db: AsyncSession,
    *,
    include_unpublished: bool = False,
    category: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[MentalHealthTopic]:
    stmt = select(MentalHealthTopic).order_by(MentalHealthTopic.name.asc())
    if not include_unpublished:
        stmt = stmt.where(MentalHealthTopic.is_published.is_(True))
    if category:
        stmt = stmt.where(MentalHealthTopic.category == category.strip().lower())
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                MentalHealthTopic.name.ilike(pattern),
                MentalHealthTopic.slug.ilike(pattern),
                # JSON array dicari via cast TEXT (portable cukup utk MySQL)
                func.cast(MentalHealthTopic.alt_names, Text).ilike(pattern),
            )
        )
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_topic_by_slug(
    db: AsyncSession,
    *,
    slug: str,
    include_unpublished: bool = False,
) -> MentalHealthTopic:
    stmt = select(MentalHealthTopic).where(
        MentalHealthTopic.slug == _normalize_slug(slug)
    )
    if not include_unpublished:
        stmt = stmt.where(MentalHealthTopic.is_published.is_(True))
    topic = (await db.execute(stmt)).scalar_one_or_none()
    if topic is None:
        raise TopicNotFoundError
    return topic


async def create_topic(
    db: AsyncSession,
    *,
    data: dict,
    admin: User,
) -> MentalHealthTopic:
    slug = _normalize_slug(data["slug"])
    existing = await db.scalar(
        select(func.count()).select_from(MentalHealthTopic).where(MentalHealthTopic.slug == slug)
    )
    if existing:
        raise TopicSlugExistsError

    topic = MentalHealthTopic(
        slug=slug,
        created_by=admin.id,
        **{k: v for k, v in data.items() if k != "slug"},
    )
    if topic.is_published and topic.published_at is None:
        topic.published_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(topic)
    await db.commit()
    await db.refresh(topic)

    # RAG semantik: embed topik yang langsung dipublish (best-effort, tanpa key = skip)
    if topic.is_published:
        from app.services.ai import embeddings as emb

        await emb.embed_and_store_topic(db, topic)
        await db.refresh(topic)
    return topic


async def update_topic(
    db: AsyncSession,
    *,
    slug: str,
    changes: dict,
) -> MentalHealthTopic:
    topic = await get_topic_by_slug(db, slug=slug, include_unpublished=True)

    was_published = topic.is_published
    for field, value in changes.items():
        setattr(topic, field, value)

    if not was_published and topic.is_published and topic.published_at is None:
        topic.published_at = datetime.now(timezone.utc).replace(tzinfo=None)
    if was_published and not topic.is_published:
        topic.published_at = None

    await db.commit()
    await db.refresh(topic)

    # RAG semantik: pastikan vektor terpasang/terbarui untuk topik published (best-effort)
    if topic.is_published:
        from app.services.ai import embeddings as emb

        await emb.embed_and_store_topic(db, topic)
        await db.refresh(topic)
    return topic


async def delete_topic(db: AsyncSession, *, slug: str) -> None:
    topic = await get_topic_by_slug(db, slug=slug, include_unpublished=True)
    await db.delete(topic)
    await db.commit()

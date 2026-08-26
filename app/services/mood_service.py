"""Service mood tracker — log harian + statistik siap-chart (pilar Kenali)."""

import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mood_log import MoodLog
from app.models.user import User


class MoodLogNotFoundError(Exception):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def create_log(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    mood_score: int,
    mood_label: str | None,
    note: str | None,
    logged_at: datetime | None = None,
) -> MoodLog:
    entry = MoodLog(
        user_id=user_id,
        mood_score=mood_score,
        mood_label=(mood_label.strip() or None) if mood_label else None,
        note=note,
        logged_at=logged_at if logged_at is not None else _utcnow(),
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def list_logs(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    days: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[MoodLog]:
    stmt = select(MoodLog).where(MoodLog.user_id == user_id)
    if days is not None:
        cutoff = _utcnow() - timedelta(days=days)
        stmt = stmt.where(MoodLog.logged_at >= cutoff)
    stmt = stmt.order_by(MoodLog.logged_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_log(db: AsyncSession, *, user_id: uuid.UUID, log_id: uuid.UUID) -> MoodLog:
    entry = (
        await db.execute(
            select(MoodLog).where(MoodLog.id == log_id, MoodLog.user_id == user_id)
        )
    ).scalar_one_or_none()
    if entry is None:
        raise MoodLogNotFoundError
    return entry


async def update_log(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    log_id: uuid.UUID,
    changes: dict,
) -> MoodLog:
    entry = await get_log(db, user_id=user_id, log_id=log_id)
    for field, value in changes.items():
        setattr(entry, field, value)
    await db.commit()
    await db.refresh(entry)
    return entry


async def delete_log(db: AsyncSession, *, user_id: uuid.UUID, log_id: uuid.UUID) -> None:
    entry = await get_log(db, user_id=user_id, log_id=log_id)
    await db.delete(entry)
    await db.commit()


async def get_stats(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    days: int = 30,
) -> dict:
    now = _utcnow()
    window_start_date = (now - timedelta(days=days - 1)).date()

    result = await db.execute(
        select(MoodLog)
        .where(MoodLog.user_id == user_id, MoodLog.logged_at >= datetime.combine(window_start_date, datetime.min.time()))
        .order_by(MoodLog.logged_at.asc())
    )
    logs = list(result.scalars().all())

    scores = [l.mood_score for l in logs if l.mood_score is not None]
    avg_score = round(sum(scores) / len(scores), 2) if scores else None

    # Tren harian: rata-rata per tanggal (beberapa log sehari diperbolehkan)
    per_day: dict["date", list[int]] = {}
    label_counter: Counter[str] = Counter()
    score_dist: Counter[int] = Counter()
    for l in logs:
        day = l.logged_at.date()
        if l.mood_score is not None:
            per_day.setdefault(day, []).append(l.mood_score)
            score_dist[l.mood_score] += 1
        if l.mood_label:
            label_counter[l.mood_label.strip()] += 1

    daily_trend = [
        {
            "date": day,
            "avg_score": round(sum(vals) / len(vals), 2),
            "count": len(vals),
        }
        for day, vals in sorted(per_day.items())
    ]

    # Streak: hari berturut-turut dengan >=1 log, anchor hari ini ATAU kemarin
    logged_dates = {day for day, _ in per_day.items()}
    streak = 0
    cursor = now.date()
    if cursor not in logged_dates:
        cursor -= timedelta(days=1)  # belum log hari ini tetap boleh lanjut streak dari kemarin
    while cursor in logged_dates:
        streak += 1
        cursor -= timedelta(days=1)

    return {
        "period_days": days,
        "total_logs": len(logs),
        "avg_score": avg_score,
        "daily_trend": daily_trend,
        "score_distribution": {str(s): c for s, c in sorted(score_dist.items())},
        "current_streak_days": streak,
        "top_labels": [
            {"label": lbl, "count": cnt}
            for lbl, cnt in label_counter.most_common(5)
        ],
    }

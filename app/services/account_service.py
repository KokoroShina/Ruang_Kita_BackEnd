"""Service akun & privasi — profil, export data, hapus akun (pilar privasi)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatSession
from app.models.journal_entry import JournalEntry
from app.models.mood_log import MoodLog
from app.models.user import User


class WrongPasswordError(Exception):
    pass


async def update_profile(
    db: AsyncSession,
    *,
    user: User,
    full_name: str | None = None,
    new_password: str | None = None,
) -> User:
    if full_name is not None:
        user.full_name = full_name.strip() or None

    if new_password:
        from app.core.security import hash_password

        user.hashed_password = hash_password(new_password)

    await db.commit()
    await db.refresh(user)
    return user


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


async def export_user_data(db: AsyncSession, *, user: User) -> dict:
    """Dump seluruh data milik user dalam satu JSON — janji transparansi privasi.

    Format field disamakan dengan response API (naive UTC ISO string).
    """
    journals = (
        await db.execute(
            select(JournalEntry)
            .where(JournalEntry.user_id == user.id)
            .order_by(JournalEntry.created_at.asc())
        )
    ).scalars().all()

    moods = (
        await db.execute(
            select(MoodLog)
            .where(MoodLog.user_id == user.id)
            .order_by(MoodLog.logged_at.asc())
        )
    ).scalars().all()

    sessions = (
        await db.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user.id)
            .order_by(ChatSession.created_at.asc())
        )
    ).scalars().all()
    session_ids = [s.id for s in sessions]
    messages_by_session: dict[uuid.UUID, list[ChatMessage]] = {}
    if session_ids:
        msgs = (
            await db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id.in_(session_ids))
                .order_by(ChatMessage.created_at.asc())
            )
        ).scalars().all()
        for m in msgs:
            messages_by_session.setdefault(m.session_id, []).append(m)

    return {
        "exported_at": _iso(_utcnow()),
        "app": "Ruang Kita",
        "note": (
            "Seluruh data yang tersimpan atas namamu. "
            "Timestamp dalam UTC; konversi WIB di frontend."
        ),
        "profile": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "consent_version": user.consent_version,
            "consent_accepted_at": _iso(user.consent_accepted_at),
            "created_at": _iso(user.created_at),
        },
        "journal_entries": [
            {
                "id": str(j.id),
                "title": j.title,
                "content": j.content,
                "ai_insight": j.ai_insight,
                "crisis_flagged": j.crisis_flagged,
                "created_at": _iso(j.created_at),
                "updated_at": _iso(j.updated_at),
            }
            for j in journals
        ],
        "mood_logs": [
            {
                "id": str(m.id),
                "mood_score": m.mood_score,
                "mood_label": m.mood_label,
                "note": m.note,
                "source": m.source,
                "logged_at": _iso(m.logged_at),
                "created_at": _iso(m.created_at),
            }
            for m in moods
        ],
        "chat_sessions": [
            {
                "id": str(s.id),
                "title": s.title,
                "status": s.status,
                "crisis_flagged": s.crisis_flagged,
                "created_at": _iso(s.created_at),
                "last_message_at": _iso(s.last_message_at),
                "messages": [
                    {
                        "id": str(msg.id),
                        "sender_role": msg.sender_role,
                        "content": msg.content,
                        "provider": msg.provider,
                        "crisis_flagged": msg.crisis_flagged,
                        "created_at": _iso(msg.created_at),
                    }
                    for msg in messages_by_session.get(s.id, [])
                ],
            }
            for s in sessions
        ],
    }


async def delete_account(db: AsyncSession, *, user: User, password: str) -> None:
    """Hard delete total (selaras pilar privasi): CASCADE menghapus journal/mood/chat;
    ai_usage_log bertahan sebagai agregat anonim via ON DELETE SET NULL."""
    from app.core.security import verify_password

    if not verify_password(password, user.hashed_password):
        raise WrongPasswordError

    await db.delete(user)
    await db.commit()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

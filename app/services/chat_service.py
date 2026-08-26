"""Service fitur Pahami — sesi chat refleksi multi-turn.

Fitur:
- send_message()              : alur non-streaming (JSON utuh)
- begin_send() + stream_reply_events() : alur streaming SSE
- _autotitle_job()            : judul sesi digenerate LLM dari pesan pertama (background)

Prinsip:
1. Pesan user SELALU disimpan dulu (tidak boleh hilang walau AI gagal).
2. Crisis input -> flag + balasan dukungan standar (tanpa AI).
3. Normal -> gateway (fallback internal), balasan disimpan setelah selesai.
4. Crisis output -> buang balasan AI, ganti pesan dukungan standar.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.chat import ChatMessage, ChatSession, ChatSessionStatus
from app.services.ai.guardrails import (
    SUPPORT_REDIRECT_TEXT,
    apply_disclaimer,
    detect_crisis,
)
from app.services.ai.prompts.chat_prompt import (
    MAX_HISTORY_MESSAGES,
    SESSION_TITLE_INSTRUCTION,
    build_chat_messages,
)
from app.services.ai.router import (
    AIGatewayError,
    AttemptInfo,
    CrisisDetectedError,
    generate_text,
)

logger = logging.getLogger(__name__)


class ChatSessionNotFoundError(Exception):
    """Sesi tidak ada ATAU milik user lain — sama-sama 404 (anti-enumeration)."""


class ChatSessionInactiveError(Exception):
    """Sesi berstatus closed/archived."""


class ChatAIUnavailableError(Exception):
    """Semua model gagal — pesan user sudah tersimpan, bisa dicoba lagi."""


CRISIS_SUPPORT_REPLY = SUPPORT_REDIRECT_TEXT

# Retensi referensi task background agar tidak di-GC (pola resmi asyncio)
_background_tasks: set[asyncio.Task] = set()


def _spawn_background(coro) -> None:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass(slots=True)
class SendResult:
    user_message: ChatMessage
    assistant_message: ChatMessage | None
    crisis_detected: bool
    model_used: str | None = None
    latency_ms: int | None = None
    attempts: list[AttemptInfo] = field(default_factory=list)
    grounded_topics: list[str] = field(default_factory=list)


@dataclass(slots=True)
class StreamStart:
    """Hasil fase awal streaming — pesan user sudah tersimpan."""

    session: ChatSession
    user_message: ChatMessage
    history: list[dict]
    input_crisis: bool
    snippets: list[str] = field(default_factory=list)          # RAG Fase 1
    grounded_topics: list[str] = field(default_factory=list)   # RAG Fase 1


async def _owned_session(
    db: AsyncSession, *, user_id: uuid.UUID, session_id: uuid.UUID
) -> ChatSession:
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id, ChatSession.user_id == user_id
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise ChatSessionNotFoundError()
    return session


async def create_session(
    db: AsyncSession, *, user_id: uuid.UUID, title: str | None = None
) -> ChatSession:
    session = ChatSession(user_id=user_id, title=title, status=ChatSessionStatus.ACTIVE.value)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def list_sessions(
    db: AsyncSession, *, user_id: uuid.UUID, limit: int = 50, offset: int = 0
) -> list[ChatSession]:
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc())
        .limit(min(limit, 100))
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_session_detail(
    db: AsyncSession, *, user_id: uuid.UUID, session_id: uuid.UUID
) -> tuple[ChatSession, list[ChatMessage]]:
    from sqlalchemy import case

    session = await _owned_session(db, user_id=user_id, session_id=session_id)
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        # Tiebreaker: pada timestamp identik (timer MySQL bisa kasar), pesan user
        # selalu mendahului balasan assistant-nya dalam satu giliran.
        .order_by(
            ChatMessage.created_at,
            case((ChatMessage.sender_role == "user", 0), else_=1),
        )
    )
    return session, list(result.scalars().all())


async def delete_session(db: AsyncSession, *, user_id: uuid.UUID, session_id: uuid.UUID) -> None:
    """Hard delete — selaras pilar privasi (user pegang kendali datanya)."""
    session = await _owned_session(db, user_id=user_id, session_id=session_id)
    await db.delete(session)  # messages ikut via ON DELETE CASCADE
    await db.commit()


def _load_history(db: AsyncSession, session_id: uuid.UUID, exclude_id: uuid.UUID | None = None):
    stmt = select(ChatMessage).where(ChatMessage.session_id == session_id)
    if exclude_id is not None:
        stmt = stmt.where(ChatMessage.id != exclude_id)
    return stmt.order_by(ChatMessage.created_at)


# ---------------------------------------------------------------------------
# Non-streaming flow
# ---------------------------------------------------------------------------
async def send_message(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    content: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> SendResult:
    session = await _owned_session(db, user_id=user_id, session_id=session_id)
    if session.status != ChatSessionStatus.ACTIVE.value:
        raise ChatSessionInactiveError()

    now = _utcnow_naive()

    # ---- 1. Simpan pesan user dulu ------------------------------------------
    input_crisis = detect_crisis(content)
    user_row = ChatMessage(
        session_id=session.id,
        sender_role="user",
        content=content,
        crisis_flagged=input_crisis.flagged,
    )
    db.add(user_row)

    # ---- 2. Crisis INPUT: jalur khusus, tanpa AI -----------------------------
    if input_crisis.flagged:
        session.crisis_flagged = True
        assistant_row = ChatMessage(
            session_id=session.id,
            sender_role="assistant",
            content=CRISIS_SUPPORT_REPLY,
            crisis_flagged=True,
        )
        db.add(assistant_row)
        session.last_message_at = now
        await db.commit()
        await db.refresh(user_row)
        await db.refresh(assistant_row)
        return SendResult(
            user_message=user_row, assistant_message=assistant_row, crisis_detected=True
        )

    await db.commit()  # pesan user aman sebelum panggil AI
    await db.refresh(user_row)

    history_rows = (await db.execute(_load_history(db, session.id, user_row.id))).scalars().all()
    history = [
        {"role": m.sender_role, "content": m.content}
        for m in list(history_rows)[-MAX_HISTORY_MESSAGES:]
    ]
    is_first_exchange = len(history) == 0

    # ---- RAG: grounding konten psikoedukasi bila topik disebut ----------------
    from app.services.ai.retriever import retrieve_context  # import lokal (hindari siklus)

    retrieval = await retrieve_context(db, content)

    # ---- 3/4. Gateway (fallback internal) ------------------------------------
    try:
        result = await generate_text(
            messages=build_chat_messages(
                history, content, context_snippets=retrieval.snippets or None
            ),
            endpoint_type="chat",
            user_id=user_id,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except CrisisDetectedError as exc:
        session.crisis_flagged = True
        assistant_row = ChatMessage(
            session_id=session.id,
            sender_role="assistant",
            content=CRISIS_SUPPORT_REPLY,
            crisis_flagged=(exc.source == "output"),
        )
        db.add(assistant_row)
        session.last_message_at = now
        await db.commit()
        await db.refresh(assistant_row)
        return SendResult(
            user_message=user_row, assistant_message=assistant_row, crisis_detected=True
        )
    except AIGatewayError as exc:
        # Semua model gagal -> 503; pesan user sudah aman tersimpan di atas.
        raise ChatAIUnavailableError(str(exc)) from exc

    assistant_row = ChatMessage(
        session_id=session.id,
        sender_role="assistant",
        content=result.content,
        provider=result.model_used[:128] if result.model_used else None,
    )
    db.add(assistant_row)
    session.last_message_at = now
    await db.commit()
    await db.refresh(assistant_row)

    if is_first_exchange and session.title is None:
        _spawn_background(_autotitle_job(session.id, user_id, content))

    return SendResult(
        user_message=user_row,
        assistant_message=assistant_row,
        crisis_detected=False,
        model_used=result.model_used,
        latency_ms=result.latency_ms,
        attempts=result.attempts,
        grounded_topics=retrieval.topic_slugs,
    )


# ---------------------------------------------------------------------------
# Streaming flow (SSE)
# ---------------------------------------------------------------------------
async def begin_send(
    db: AsyncSession, *, user_id: uuid.UUID, session_id: uuid.UUID, content: str
) -> StreamStart:
    """Fase 1 streaming: validasi + simpan pesan user SEBELUM stream dimulai."""
    session = await _owned_session(db, user_id=user_id, session_id=session_id)
    if session.status != ChatSessionStatus.ACTIVE.value:
        raise ChatSessionInactiveError()

    input_crisis = detect_crisis(content)
    user_row = ChatMessage(
        session_id=session.id,
        sender_role="user",
        content=content,
        crisis_flagged=input_crisis.flagged,
    )
    db.add(user_row)
    now = _utcnow_naive()

    if input_crisis.flagged:
        session.crisis_flagged = True
        canned = ChatMessage(
            session_id=session.id,
            sender_role="assistant",
            content=CRISIS_SUPPORT_REPLY,
            crisis_flagged=True,
        )
        db.add(canned)
        session.last_message_at = now
        await db.commit()
        await db.refresh(user_row)
        await db.refresh(canned)
        return StreamStart(session=session, user_message=user_row, history=[], input_crisis=True)

    await db.commit()
    await db.refresh(user_row)

    history_rows = (await db.execute(_load_history(db, session.id, user_row.id))).scalars().all()
    history = [
        {"role": m.sender_role, "content": m.content}
        for m in list(history_rows)[-MAX_HISTORY_MESSAGES:]
    ]

    # RAG: retrieval di fase awal supaya FE bisa tahu grounding sejak event pertama
    from app.services.ai.retriever import retrieve_context  # import lokal (hindari siklus)

    retrieval = await retrieve_context(db, content)

    return StreamStart(
        session=session,
        user_message=user_row,
        history=history,
        input_crisis=False,
        snippets=retrieval.snippets,
        grounded_topics=retrieval.topic_slugs,
    )


async def _persist_assistant(
    *,
    session_id: uuid.UUID,
    content: str,
    provider: str | None,
    crisis_flagged: bool = False,
    mark_session_crisis: bool = False,
) -> str:
    """Simpan balasan assistant dengan session DB sendiri (di luar request-scoped)."""
    async with AsyncSessionLocal() as s2:
        row = ChatMessage(
            session_id=session_id,
            sender_role="assistant",
            content=content,
            provider=provider,
            crisis_flagged=crisis_flagged,
        )
        s2.add(row)
        if mark_session_crisis:
            await s2.execute(
                update(ChatSession)
                .where(ChatSession.id == session_id)
                .values(crisis_flagged=True, last_message_at=_utcnow_naive())
            )
        else:
            await s2.execute(
                update(ChatSession)
                .where(ChatSession.id == session_id)
                .values(last_message_at=_utcnow_naive())
            )
        await s2.commit()
        await s2.refresh(row)
        return str(row.id)


async def stream_reply_events(
    start: StreamStart,
    *,
    user_id: uuid.UUID,
    temperature: float | None = None,
    max_tokens: int | None = None,
):
    """Fase 2 streaming: yield event dict -> layer API memformat jadi SSE.

    Event: meta / model / delta / crisis / done / error.
    Persistensi balasan dilakukan DI SINI dengan session DB sendiri.
    """
    from app.services.ai.router import stream_text  # import lokal (hindari siklus)

    yield {
        "event": "meta",
        "data": {
            "session_id": str(start.session.id),
            "user_message_id": str(start.user_message.id),
            "input_crisis": start.input_crisis,
        },
    }

    # RAG: beri tahu FE topik grounding SEBELUM delta pertama
    if start.grounded_topics:
        yield {"event": "grounded", "data": {"topics": start.grounded_topics}}

    if start.input_crisis:
        # Canned reply sudah tersimpan oleh begin_send
        yield {"event": "delta", "data": {"text": CRISIS_SUPPORT_REPLY}}
        yield {
            "event": "done",
            "data": {
                "crisis_detected": True,
                "assistant_message_id": str(start.user_message.id),  # placeholder, diabaikan klien
                "attempts": [],
            },
        }
        return

    parts: list[str] = []
    done_payload: dict | None = None
    try:
        async for kind, payload in stream_text(
            messages=build_chat_messages(
                start.history,
                start.user_message.content,
                context_snippets=start.snippets or None,
            ),
            endpoint_type="chat",
            user_id=user_id,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            if kind == "model":
                yield {"event": "model", "data": payload}
            elif kind == "delta":
                parts.append(payload["text"])
                yield {"event": "delta", "data": payload}
            elif kind == "crisis":
                # Partial dibuang (tidak disimpan) — ganti pesan dukungan standar
                row_id = await _persist_assistant(
                    session_id=start.session.id,
                    content=CRISIS_SUPPORT_REPLY,
                    provider=None,
                    crisis_flagged=True,
                    mark_session_crisis=True,
                )
                yield {"event": "crisis", "data": {"reply": CRISIS_SUPPORT_REPLY}}
                yield {
                    "event": "done",
                    "data": {
                        "crisis_detected": True,
                        "assistant_message_id": row_id,
                        "attempts": payload.get("attempts", []),
                    },
                }
                return
            elif kind == "done":
                done_payload = payload
    except Exception:  # noqa: BLE001
        logger.exception("Streaming chat gagal")
        yield {
            "event": "error",
            "data": {"detail": "AI terputus di tengah jalan. Pesanmu tetap tersimpan."},
        }
        return

    if not parts or done_payload is None:
        yield {"event": "error", "data": {"detail": "AI tidak mengirim jawaban. Coba lagi ya."}}
        return

    # Disclaimer ditambahkan sebagai delta terakhir (server-controlled)
    suffix = apply_disclaimer("", "chat")
    parts.append(suffix)
    yield {"event": "delta", "data": {"text": suffix}}

    full_content = "".join(parts)
    model_used = done_payload.get("model_used")
    row_id = await _persist_assistant(
        session_id=start.session.id,
        content=full_content,
        provider=model_used[:128] if model_used else None,
    )

    if len(start.history) == 0 and start.session.title is None:
        _spawn_background(_autotitle_job(start.session.id, user_id, start.user_message.content))

    yield {
        "event": "done",
        "data": {
            "crisis_detected": False,
            "assistant_message_id": row_id,
            "model_used": model_used,
            "latency_ms": done_payload.get("latency_ms"),
            "attempts": done_payload.get("attempts", []),
            "grounded_topics": start.grounded_topics,
        },
    }


# ---------------------------------------------------------------------------
# Auto-title (background)
# ---------------------------------------------------------------------------
def _sanitize_title(raw: str) -> str:
    title = raw.strip().strip("\"'`“”‘’").replace("\r", " ").replace("\n", " ").strip()
    return title[:120].strip()


async def _autotitle_job(session_id: uuid.UUID, user_id: uuid.UUID, first_user_content: str) -> None:
    """Generate judul sesi dari pesan pertama. Gagal = biarkan title tetap NULL."""
    try:
        result = await generate_text(
            messages=[
                {"role": "system", "content": SESSION_TITLE_INSTRUCTION},
                {"role": "user", "content": first_user_content[:1500]},
            ],
            endpoint_type="session_title",
            user_id=user_id,
            temperature=0.3,
            max_tokens=32,
        )
        title = _sanitize_title(result.content)
        if not title:
            return
        async with AsyncSessionLocal() as s2:
            await s2.execute(
                update(ChatSession)
                .where(ChatSession.id == session_id, ChatSession.title.is_(None))
                .values(title=title)
            )
            await s2.commit()
        logger.info("Auto-title tersimpan utk sesi %s: %r", session_id, title)
    except Exception:  # noqa: BLE001
        logger.warning("Auto-title gagal (diabaikan) utk sesi %s", session_id, exc_info=True)


__all__ = [
    "ChatAIUnavailableError",
    "ChatSessionInactiveError",
    "ChatSessionNotFoundError",
    "SendResult",
    "StreamStart",
    "begin_send",
    "create_session",
    "delete_session",
    "get_session_detail",
    "list_sessions",
    "send_message",
    "stream_reply_events",
]

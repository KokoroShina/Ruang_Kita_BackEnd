"""Endpoint fitur Pahami — chatbot refleksi multi-turn (semua endpoint protected)."""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.core.dependencies import CurrentUser, DbSession
from app.schemas.chat import (
    ChatMessageRead,
    ChatSendResponse,
    ChatSendMessage,
    ChatSessionCreate,
    ChatSessionDetailRead,
    ChatSessionRead,
)
from app.services.ai.openrouter_client import OpenRouterAuthError
from app.services.ai.router import AIConfigurationError
from app.services import chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post(
    "/sessions",
    response_model=ChatSessionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Buat sesi chat baru",
)
async def create_session(
    payload: ChatSessionCreate, current_user: CurrentUser, db: DbSession
):
    return await chat_service.create_session(db, user_id=current_user.id, title=payload.title)


@router.get(
    "/sessions",
    response_model=list[ChatSessionRead],
    summary="Daftar sesi chat saya (terbaru dulu)",
)
async def list_sessions(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return await chat_service.list_sessions(
        db, user_id=current_user.id, limit=limit, offset=offset
    )


@router.get(
    "/sessions/{session_id}",
    response_model=ChatSessionDetailRead,
    summary="Detail sesi + seluruh pesan",
)
async def get_session_detail(
    session_id: uuid.UUID, current_user: CurrentUser, db: DbSession
):
    try:
        session, messages = await chat_service.get_session_detail(
            db, user_id=current_user.id, session_id=session_id
        )
    except chat_service.ChatSessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sesi chat tidak ditemukan",
        ) from None
    # Konstruksi eksplisit — JANGAN model_validate(ORM) langsung karena field
    # `messages` memicu lazy-load relasi (MissingGreenlet di async SQLAlchemy).
    base = ChatSessionRead.model_validate(session).model_dump()
    return ChatSessionDetailRead(
        **base,
        messages=[ChatMessageRead.model_validate(m) for m in messages],
    )


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Hapus sesi (beserta semua pesannya)",
)
async def delete_session(session_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> None:
    try:
        await chat_service.delete_session(db, user_id=current_user.id, session_id=session_id)
    except chat_service.ChatSessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sesi chat tidak ditemukan",
        ) from None


@router.post(
    "/sessions/{session_id}/messages/stream",
    summary="Kirim pesan -> balasan AI streaming (Server-Sent Events)",
    response_model=None,
)
async def send_message_stream(
    session_id: uuid.UUID,
    payload: ChatSendMessage,
    current_user: CurrentUser,
    db: DbSession,
):
    """Event SSE: `meta`, `model`, `delta` (berulang), `crisis`, `done`, `error`.

    Pesan user tersimpan SEBELUM stream dimulai — walau AI gagal, pesan tetap aman.
    """
    try:
        start = await chat_service.begin_send(
            db, user_id=current_user.id, session_id=session_id, content=payload.content
        )
    except chat_service.ChatSessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sesi chat tidak ditemukan",
        ) from None
    except chat_service.ChatSessionInactiveError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sesi sudah ditutup/diarsipkan",
        ) from None

    async def event_stream():
        async for evt in chat_service.stream_reply_events(
            start,
            user_id=current_user.id,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
        ):
            yield _sse(evt["event"], evt["data"])

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ChatSendResponse,
    summary="Kirim pesan -> balasan AI refleksi (multi-turn)",
)
async def send_message(
    session_id: uuid.UUID,
    payload: ChatSendMessage,
    current_user: CurrentUser,
    db: DbSession,
) -> ChatSendResponse:
    try:
        result = await chat_service.send_message(
            db,
            user_id=current_user.id,
            session_id=session_id,
            content=payload.content,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
        )
    except chat_service.ChatSessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sesi chat tidak ditemukan",
        ) from None
    except chat_service.ChatSessionInactiveError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sesi sudah ditutup/diarsipkan",
        ) from None
    except chat_service.ChatAIUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "AI sedang tidak tersedia, coba lagi sebentar. "
                "Pesanmu tetap tersimpan di riwayat."
            ),
        ) from exc
    except (AIConfigurationError, OpenRouterAuthError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Konfigurasi AI bermasalah: {exc}",
        ) from exc

    return ChatSendResponse(
        crisis_detected=result.crisis_detected,
        user_message=ChatMessageRead.model_validate(result.user_message),
        assistant_message=(
            ChatMessageRead.model_validate(result.assistant_message)
            if result.assistant_message
            else None
        ),
        model_used=result.model_used,
        latency_ms=result.latency_ms,
        attempts=[{"model": a.model, "ok": a.ok, "error": a.error} for a in result.attempts],
        grounded_topics=result.grounded_topics,
    )

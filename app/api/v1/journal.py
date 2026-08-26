"""Endpoint fitur Kenali — jurnal + analisis AI one-shot (semua protected)."""

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.core.dependencies import CurrentUser, DbSession
from app.schemas.journal import (
    JournalAnalyzeRequest,
    JournalAnalyzeResponse,
    JournalEntryCreate,
    JournalEntryRead,
    JournalEntryUpdate,
)
from app.services.ai.openrouter_client import OpenRouterAuthError
from app.services.ai.router import AIConfigurationError, AIGatewayError
from app.services import journal_service

router = APIRouter(prefix="/journal", tags=["journal"])


@router.post(
    "/entries",
    response_model=JournalEntryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Tulis entri jurnal baru",
)
async def create_entry(payload: JournalEntryCreate, current_user: CurrentUser, db: DbSession):
    return await journal_service.create_entry(
        db, user_id=current_user.id, content=payload.content, title=payload.title
    )


@router.get(
    "/entries",
    response_model=list[JournalEntryRead],
    summary="Daftar jurnal saya (terbaru dulu)",
)
async def list_entries(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return await journal_service.list_entries(
        db, user_id=current_user.id, limit=limit, offset=offset
    )


@router.get(
    "/entries/{entry_id}",
    response_model=JournalEntryRead,
    summary="Detail entri jurnal",
)
async def get_entry(entry_id: uuid.UUID, current_user: CurrentUser, db: DbSession):
    try:
        return await journal_service.get_entry(db, user_id=current_user.id, entry_id=entry_id)
    except journal_service.JournalEntryNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entri jurnal tidak ditemukan",
        ) from None


@router.put(
    "/entries/{entry_id}",
    response_model=JournalEntryRead,
    summary="Ubah judul/konten entri (konten berubah -> insight dibuang)",
)
async def update_entry(
    entry_id: uuid.UUID, payload: JournalEntryUpdate, current_user: CurrentUser, db: DbSession
):
    try:
        return await journal_service.update_entry(
            db,
            user_id=current_user.id,
            entry_id=entry_id,
            title=payload.title,
            content=payload.content,
        )
    except journal_service.JournalEntryNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entri jurnal tidak ditemukan",
        ) from None


@router.delete(
    "/entries/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Hapus entri jurnal",
)
async def delete_entry(entry_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> None:
    try:
        await journal_service.delete_entry(db, user_id=current_user.id, entry_id=entry_id)
    except journal_service.JournalEntryNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entri jurnal tidak ditemukan",
        ) from None


@router.post(
    "/entries/{entry_id}/analyze",
    response_model=JournalAnalyzeResponse,
    summary="Analisis entri via AI -> insight refleksi (bisa dipanggil ulang)",
)
async def analyze_entry(
    entry_id: uuid.UUID,
    payload: JournalAnalyzeRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> JournalAnalyzeResponse:
    try:
        result = await journal_service.analyze_entry(
            db,
            user_id=current_user.id,
            entry_id=entry_id,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
        )
    except journal_service.JournalEntryNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entri jurnal tidak ditemukan",
        ) from None
    except AIGatewayError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI sedang tidak tersedia: {exc}",
        ) from exc
    except (AIConfigurationError, OpenRouterAuthError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Konfigurasi AI bermasalah: {exc}",
        ) from exc

    return JournalAnalyzeResponse(
        crisis_detected=result.crisis_detected,
        entry=JournalEntryRead.model_validate(result.entry),
        model_used=result.model_used,
        latency_ms=result.latency_ms,
        attempts=[{"model": a.model, "ok": a.ok, "error": a.error} for a in result.attempts],
        grounded_topics=result.grounded_topics,
    )

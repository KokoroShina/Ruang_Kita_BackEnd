"""Endpoint mood tracker (pilar Kenali) — semua protected."""

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.core.dependencies import CurrentUser, DbSession
from app.schemas.mood import MoodLogCreate, MoodLogRead, MoodLogUpdate, MoodStatsResponse
from app.services import mood_service

router = APIRouter(prefix="/mood", tags=["mood"])


@router.post(
    "/logs",
    response_model=MoodLogRead,
    status_code=status.HTTP_201_CREATED,
    summary="Catat mood (score 1-5 + label opsional)",
)
async def create_log(payload: MoodLogCreate, current_user: CurrentUser, db: DbSession):
    return await mood_service.create_log(
        db,
        user_id=current_user.id,
        mood_score=payload.mood_score,
        mood_label=payload.mood_label,
        note=payload.note,
        logged_at=payload.logged_at,
    )


@router.get(
    "/logs",
    response_model=list[MoodLogRead],
    summary="Riwayat mood saya (terbaru dulu)",
)
async def list_logs(
    current_user: CurrentUser,
    db: DbSession,
    days: int | None = Query(default=None, ge=1, le=365, description="Filter rentang hari terakhir"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return await mood_service.list_logs(
        db, user_id=current_user.id, days=days, limit=limit, offset=offset
    )


@router.patch(
    "/logs/{log_id}",
    response_model=MoodLogRead,
    summary="Ubah log mood milik sendiri",
)
async def update_log(
    log_id: uuid.UUID, payload: MoodLogUpdate, current_user: CurrentUser, db: DbSession
):
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Tidak ada field yang dikirim untuk diubah",
        )
    try:
        return await mood_service.update_log(
            db, user_id=current_user.id, log_id=log_id, changes=changes
        )
    except mood_service.MoodLogNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Log mood tidak ditemukan",
        ) from None


@router.delete(
    "/logs/{log_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Hapus log mood milik sendiri",
)
async def delete_log(log_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> None:
    try:
        await mood_service.delete_log(db, user_id=current_user.id, log_id=log_id)
    except mood_service.MoodLogNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Log mood tidak ditemukan",
        ) from None


@router.get(
    "/stats",
    response_model=MoodStatsResponse,
    summary="Statistik mood (tren harian, distribusi, streak, label teratas)",
)
async def get_stats(
    current_user: CurrentUser,
    db: DbSession,
    days: int = Query(default=30, ge=7, le=365),
):
    return await mood_service.get_stats(db, user_id=current_user.id, days=days)

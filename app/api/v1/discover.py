"""Endpoint Temukan — rekomendasi rule-based + browse/kelola content library."""

from fastapi import APIRouter, HTTPException, Query, status

from app.core.dependencies import AdminUser, CurrentUser, DbSession
from app.schemas.discover import (
    ContentItemCreate,
    ContentItemRead,
    ContentItemUpdate,
    DiscoverResponse,
)
from app.services import discover_service

router = APIRouter(tags=["discover"])


# ===== Rekomendasi =====


@router.get(
    "/discover/recommendations",
    response_model=DiscoverResponse,
    summary="Rekomendasi personal rule-based (dari mood & jurnal terbaru)",
)
async def get_recommendations(
    current_user: CurrentUser,
    db: DbSession,
    max_topics: int = Query(default=3, ge=1, le=5),
    max_content: int = Query(default=4, ge=1, le=8),
):
    return await discover_service.build_recommendations(
        db, user_id=current_user.id, max_topics=max_topics, max_content=max_content
    )


# ===== Browse konten (protected) =====


@router.get(
    "/content",
    response_model=list[ContentItemRead],
    summary="Browse konten psikoedukasi published (filter type/topic/q)",
)
async def list_content(
    current_user: CurrentUser,
    db: DbSession,
    content_type: str | None = Query(default=None, max_length=32),
    topic: str | None = Query(default=None, max_length=120),
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return await discover_service.list_content(
        db,
        include_unpublished=False,
        content_type=content_type,
        topic=topic,
        q=q,
        limit=limit,
        offset=offset,
    )


# ===== Admin content library =====


@router.post(
    "/admin/content",
    response_model=ContentItemRead,
    status_code=status.HTTP_201_CREATED,
    summary="[Admin] Tambah item konten",
)
async def admin_create_content(payload: ContentItemCreate, admin: AdminUser, db: DbSession):
    try:
        return await discover_service.create_content(db, data=payload.model_dump())
    except discover_service.ContentSlugExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Slug sudah dipakai: {payload.slug}",
        ) from None


@router.patch(
    "/admin/content/{slug}",
    response_model=ContentItemRead,
    summary="[Admin] Ubah item konten",
)
async def admin_update_content(slug: str, payload: ContentItemUpdate, admin: AdminUser, db: DbSession):
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Tidak ada field yang dikirim untuk diubah",
        )
    try:
        return await discover_service.update_content(db, slug=slug, changes=changes)
    except discover_service.ContentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Konten tidak ditemukan",
        ) from None


@router.delete(
    "/admin/content/{slug}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="[Admin] Hapus item konten",
)
async def admin_delete_content(slug: str, admin: AdminUser, db: DbSession) -> None:
    try:
        await discover_service.delete_content(db, slug=slug)
    except discover_service.ContentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Konten tidak ditemukan",
        ) from None

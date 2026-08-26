"""Endpoint ensiklopedia kesehatan mental (protected read + admin CRUD)."""

from fastapi import APIRouter, HTTPException, Query, status

from app.core.dependencies import AdminUser, CurrentUser, DbSession
from app.schemas.topic import TopicCreate, TopicRead, TopicUpdate
from app.services import topic_service

router = APIRouter(tags=["topics"])


# ===== Publik (protected read — hanya published) =====


@router.get(
    "/topics",
    response_model=list[TopicRead],
    summary="Daftar topik published (filter category + cari q)",
)
async def list_topics(
    current_user: CurrentUser,
    db: DbSession,
    category: str | None = Query(default=None, max_length=32),
    q: str | None = Query(default=None, max_length=100, description="Cari nama/slug/istilah populer"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return await topic_service.list_topics(
        db, include_unpublished=False, category=category, q=q, limit=limit, offset=offset
    )


@router.get("/topics/{slug}", response_model=TopicRead, summary="Detail topik by slug")
async def get_topic(slug: str, current_user: CurrentUser, db: DbSession):
    try:
        return await topic_service.get_topic_by_slug(db, slug=slug, include_unpublished=False)
    except topic_service.TopicNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topik tidak ditemukan",
        ) from None


# ===== Admin (gate ADMIN_EMAILS) =====


@router.post(
    "/admin/topics",
    response_model=TopicRead,
    status_code=status.HTTP_201_CREATED,
    summary="[Admin] Buat topik baru",
)
async def admin_create_topic(payload: TopicCreate, admin: AdminUser, db: DbSession):
    try:
        return await topic_service.create_topic(db, data=payload.model_dump(), admin=admin)
    except topic_service.TopicSlugExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Slug sudah dipakai: {payload.slug}",
        ) from None


@router.patch(
    "/admin/topics/{slug}",
    response_model=TopicRead,
    summary="[Admin] Update sebagian field topik",
)
async def admin_update_topic(slug: str, payload: TopicUpdate, admin: AdminUser, db: DbSession):
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Tidak ada field yang dikirim untuk diubah",
        )
    try:
        return await topic_service.update_topic(db, slug=slug, changes=changes)
    except topic_service.TopicNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topik tidak ditemukan",
        ) from None


@router.delete(
    "/admin/topics/{slug}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="[Admin] Hapus topik",
)
async def admin_delete_topic(slug: str, admin: AdminUser, db: DbSession) -> None:
    try:
        await topic_service.delete_topic(db, slug=slug)
    except topic_service.TopicNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topik tidak ditemukan",
        ) from None

"""Endpoint akun & privasi — profil, export data, hapus akun (semua protected)."""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from app.core.dependencies import CurrentUser, DbSession
from app.models.user import User
from app.schemas.user import DeleteAccountConfirm, ProfileUpdate, UserRead
from app.services import account_service

router = APIRouter(tags=["account"])


@router.patch(
    "/auth/me",
    response_model=UserRead,
    summary="Ubah profil (nama dan/atau password)",
)
async def update_me(payload: ProfileUpdate, current_user: CurrentUser, db: DbSession) -> User:
    if payload.new_password is not None:
        from app.core.security import verify_password

        if not verify_password(payload.current_password or "", current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password sekarang salah",
            )

    return await account_service.update_profile(
        db,
        user=current_user,
        full_name=payload.full_name,
        new_password=payload.new_password,
    )


@router.get(
    "/me/export",
    summary="Unduh seluruh data pribadi (JSON) — hak portabilitas data",
)
async def export_me(current_user: CurrentUser, db: DbSession) -> JSONResponse:
    data = await account_service.export_user_data(db, user=current_user)
    stamp = (data["exported_at"] or "").split("T")[0]
    return JSONResponse(
        content=data,
        headers={
            "Content-Disposition": f'attachment; filename="ruangkita-export-{stamp}.json"'
        },
    )


@router.delete(
    "/account",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Hapus akun + SELURUH data secara permanen",
)
async def delete_account(
    payload: DeleteAccountConfirm, current_user: CurrentUser, db: DbSession
) -> None:
    """Hard delete tanpa grace period — sesuai pilar privasi Ruang Kita.

    Jurnal, mood log, chat (beserta pesannya) ikut terhapus via CASCADE.
    Log agregat ai_usage_log bertahan sebagai data anonim (FK SET NULL).
    """
    try:
        await account_service.delete_account(db, user=current_user, password=payload.password)
    except account_service.WrongPasswordError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password salah — akun tidak dihapus",
        ) from None

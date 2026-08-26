import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User

http_bearer = HTTPBearer(
    auto_error=False,
    description="Paste access token dari POST /api/v1/auth/login",
)

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Token tidak valid atau sudah kedaluwarsa",
    headers={"WWW-Authenticate": "Bearer"},
)

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(http_bearer)],
    db: DbSession,
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _CREDENTIALS_EXCEPTION

    try:
        payload = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        raise _CREDENTIALS_EXCEPTION from None

    subject = payload.get("sub")
    if not subject:
        raise _CREDENTIALS_EXCEPTION

    try:
        user_id = uuid.UUID(str(subject))
    except ValueError:
        raise _CREDENTIALS_EXCEPTION from None

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise _CREDENTIALS_EXCEPTION
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def is_admin_email(email: str) -> bool:
    """True bila email terdaftar di ADMIN_EMAILS (.env) — daftar kosong berarti belum ada admin.

    Dipakai bersama oleh gate get_current_admin dan flag is_admin di respons auth/profil.
    """
    from app.core.config import settings

    admin_emails = {e.strip().lower() for e in settings.ADMIN_EMAILS if e.strip()}
    return bool(admin_emails) and email.strip().lower() in admin_emails


async def get_current_admin(current_user: CurrentUser) -> User:
    """Gate konten admin (ensiklopedia): email user harus terdaftar di ADMIN_EMAILS (.env).

    Kosong = belum ada admin -> selalu 403. Perbandingan case-insensitive.
    """
    if not is_admin_email(current_user.email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akses khusus admin",
        )
    return current_user


AdminUser = Annotated[User, Depends(get_current_admin)]

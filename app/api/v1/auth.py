from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.core.dependencies import CurrentUser, DbSession, is_admin_email
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrasi akun baru (email + password)",
)
async def register(payload: UserCreate, db: DbSession) -> User:
    email = payload.email.lower()

    existing = await db.scalar(select(func.count()).select_from(User).where(User.email == email))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email sudah terdaftar",
        )

    user = User(
        email=email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        consent_version=payload.consent_version,
        consent_accepted_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login → access token JWT",
)
async def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    email = payload.email.lower()
    user = await db.scalar(select(User).where(User.email == email))

    # Pesan error generik — hindari user enumeration
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email atau password salah",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun tidak aktif",
        )

    return TokenResponse(
        access_token=create_access_token(user.id), is_admin=is_admin_email(email)
    )


@router.get("/me", response_model=UserRead, summary="Profil user dari token")
async def get_me(current_user: CurrentUser) -> User:
    return current_user

"""Password hashing (bcrypt langsung) & JWT (PyJWT).

Catatan desain:
- bcrypt dipakai langsung, TANPA passlib (known issue passlib vs bcrypt>=4).
- bcrypt hanya memproses maksimal 72 byte password → divalidasi eksplisit.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import settings

BCRYPT_MAX_PASSWORD_BYTES = 72
_BCRYPT_ROUNDS = 12


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError(f"Password maksimal {BCRYPT_MAX_PASSWORD_BYTES} byte (bcrypt limit)")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except ValueError:
        return False


def create_access_token(subject: str | uuid.UUID, expires_minutes: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Raise jwt.ExpiredSignatureError / jwt.InvalidTokenError jika tidak valid."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])

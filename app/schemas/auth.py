from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    # Flag UX utk frontend (tampilkan menu admin) — otorisasi tetap dicek server per request
    is_admin: bool = False

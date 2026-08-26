import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, model_validator


class UserBase(BaseModel):
    email: EmailStr
    full_name: str | None = Field(default=None, max_length=255)


class UserCreate(UserBase):
    password: str = Field(
        min_length=8,
        max_length=72,
        description="Minimal 8 karakter (batas atas 72 mengikuti limit byte bcrypt)",
    )
    consent_version: str = Field(
        default="v1",
        max_length=32,
        description="Versi kebijakan privasi & ketentuan layanan yang disetujui user",
    )


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool
    consent_version: str | None
    consent_accepted_at: datetime | None
    created_at: datetime

    @computed_field
    @property
    def is_admin(self) -> bool:
        """Status admin mengikuti ADMIN_EMAILS (.env), bukan kolom DB — dipakai frontend utk UI admin."""
        from app.core.dependencies import is_admin_email

        return is_admin_email(self.email)


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    # Ganti password opsional — wajib sertakan password sekarang utk verifikasi
    current_password: str | None = Field(default=None, min_length=1, max_length=72)
    new_password: str | None = Field(default=None, min_length=8, max_length=72)

    @model_validator(mode="after")
    def _password_pair(self) -> "ProfileUpdate":
        if self.new_password is not None and self.current_password is None:
            raise ValueError("new_password wajib disertai current_password")
        return self


class DeleteAccountConfirm(BaseModel):
    password: str = Field(min_length=1, max_length=72)

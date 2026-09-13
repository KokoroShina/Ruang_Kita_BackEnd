import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Pola URL YouTube yang diterima — ID diekstrak frontend untuk embed.
# Format: watch?v=, youtu.be/, shorts/, embed/, live/
_YOUTUBE_URL_RE = re.compile(
    r"^(?:https?://)?"
    r"(?:www\.|m\.)?"
    r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|embed/|live/)"
    r"|youtu\.be/)"
    r"[A-Za-z0-9_-]{6,20}"
    r"(?:[?&#].*)?$"
)


def _validate_youtube_url(value: str | None) -> str | None:
    """Normalisasi + validasi URL YouTube — dipakai TopicBase & TopicUpdate.

    String kosong ('') diinterpretasi service sebagai sinyal hapus (konsisten
    dengan perilaku image_url di BFF admin).
    """
    if value is None:
        return value
    normalized = value.strip()
    if not normalized:
        return normalized
    if not _YOUTUBE_URL_RE.fullmatch(normalized):
        raise ValueError(
            "URL video harus URL YouTube valid "
            "(contoh: https://www.youtube.com/watch?v=... atau https://youtu.be/...)"
        )
    return normalized


class TopicBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    alt_names: list[str] = Field(default_factory=list, max_length=20)
    category: str = Field(
        default="other",
        max_length=32,
        description="mood | anxiety | personality | trauma | eating | burnout | other",
    )
    summary: str = Field(min_length=1, max_length=2000)
    signs_symptoms: list[str] = Field(default_factory=list, max_length=30)
    causes_risk_factors: str | None = Field(default=None, max_length=5000)
    coping_treatment: str | None = Field(default=None, max_length=8000)
    myths_facts: list[dict] = Field(default_factory=list, max_length=15)
    when_to_seek_help: str | None = Field(default=None, max_length=3000)
    support_resources: list[dict] = Field(default_factory=list, max_length=10)
    related_topic_slugs: list[str] = Field(default_factory=list, max_length=20)
    sources: str | None = Field(default=None, max_length=2000)
    image_url: str | None = Field(
        default=None,
        max_length=500,
        description="URL gambar cover atau path upload lokal. Opsional.",
    )
    video_url: str | None = Field(
        default=None,
        max_length=500,
        description=(
            "URL video YouTube penjelasan topik. Opsional. "
            "String kosong ('') berarti hapus."
        ),
    )
    language: str = Field(default="id", min_length=2, max_length=8)

    @field_validator("video_url")
    @classmethod
    def _video_url_check(cls, value: str | None) -> str | None:
        return _validate_youtube_url(value)


class TopicCreate(TopicBase):
    slug: str = Field(
        min_length=2,
        max_length=120,
        pattern=r"^[A-Za-z0-9]+(-[A-Za-z0-9]+)*$",
        description="URL-safe; huruf besar otomatis dinormalisasi ke lowercase. Contoh: ptsd",
    )
    is_published: bool = False


class TopicUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    alt_names: list[str] | None = Field(default=None, max_length=20)
    category: str | None = Field(default=None, max_length=32)
    summary: str | None = Field(default=None, min_length=1, max_length=2000)
    signs_symptoms: list[str] | None = Field(default=None, max_length=30)
    causes_risk_factors: str | None = Field(default=None, max_length=5000)
    coping_treatment: str | None = Field(default=None, max_length=8000)
    myths_facts: list[dict] | None = Field(default=None, max_length=15)
    when_to_seek_help: str | None = Field(default=None, max_length=3000)
    support_resources: list[dict] | None = Field(default=None, max_length=10)
    related_topic_slugs: list[str] | None = Field(default=None, max_length=20)
    sources: str | None = Field(default=None, max_length=2000)
    image_url: str | None = Field(
        default=None,
        max_length=500,
        description="Kirim string kosong ('') untuk menghapus gambar.",
    )
    video_url: str | None = Field(
        default=None,
        max_length=500,
        description="Kirim string kosong ('') untuk menghapus video.",
    )
    language: str | None = Field(default=None, min_length=2, max_length=8)
    is_published: bool | None = None

    @field_validator("video_url")
    @classmethod
    def _video_url_check(cls, value: str | None) -> str | None:
        return _validate_youtube_url(value)


class TopicRead(TopicBase):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    is_published: bool
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime

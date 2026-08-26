from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ===== App =====
    PROJECT_NAME: str = "Ruang Kita API"
    ENVIRONMENT: str = "development"  # development | staging | production
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ===== Database =====
    # Contoh format: mysql+aiomysql://user:password@localhost:3306/ruang_kita_db
    DATABASE_URL: str = "mysql+aiomysql://root@localhost:3306/ruang_kita_db"

    # ===== Security / JWT =====
    JWT_SECRET: str = "dev-only-secret-change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 hari

    # ===== AI Providers (dipakai fase berikutnya — AI Gateway) =====
    GEMINI_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None

    # ===== AI Gateway (OpenRouter) =====
    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    AI_TIMEOUT_SECONDS: float = 90.0
    # Matikan mode reasoning di model yang mendukungnya -> jawaban langsung tanpa
    # "leakage" proses berpikir (penting utk chatbot). Set false kalau butuh reasoning.
    AI_DISABLE_REASONING: bool = True
    AI_MODEL_DEFAULT: str = "dots-studio/dots-3-note-preview:free"
    # Dicoba berurutan setelah default saat rate limit / error (format JSON array di .env)
    AI_MODEL_FALLBACKS: list[str] = [
        "nvidia/nemotron-3-nano-30b-a3b:free",
        "z-ai/glm-5.2:free",
        "google/gemma-4-31b-it:free",
        "openrouter/free",
    ]

    # ===== Admin =====
    # Email dalam list ini boleh mengelola konten ensiklopedia (/admin/topics).
    # Kosong = belum ada admin (endpoint admin akan selalu 403).
    ADMIN_EMAILS: list[str] = []

    # ===== Importer konten massal (scripts/import_topics_bulk.py) =====
    # Kredensial akun admin yang dipakai skrip impor massal untuk login + POST
    # /admin/topics. Emailnya wajib terdaftar di ADMIN_EMAILS di atas.
    IMPORT_ADMIN_EMAIL: str | None = None
    IMPORT_ADMIN_PASSWORD: str | None = None

    # ===== Logging =====
    # File log harian: <LOG_DIR>/app.log (rotasi tengah malam, backup LOG_RETENTION_DAYS hari)
    LOG_LEVEL: str = "INFO"  # DEBUG | INFO | WARNING | ERROR
    LOG_DIR: str = "logs"
    LOG_RETENTION_DAYS: int = 14

    # ===== RAG semantik (Fase 2 — embeddings) =====
    # Isi GEMINI_API_KEY (gratis: https://aistudio.google.com/apikey) untuk mengaktifkan
    # retrieval semantik. Tanpa key, sistem otomatis memakai retrieval leksikal saja.
    EMBEDDING_MODEL: str = "text-embedding-004"
    EMBEDDING_SIMILARITY_THRESHOLD: float = 0.55
    RAG_SEMANTIC_ENABLED: bool = True

    @property
    def ai_model_candidates(self) -> list[str]:
        """Default + fallback, tanpa duplikat — urutan prioritas pemanggilan."""
        seen: set[str] = set()
        candidates: list[str] = []
        for model in [self.AI_MODEL_DEFAULT, *self.AI_MODEL_FALLBACKS]:
            if model and model not in seen:
                seen.add(model)
                candidates.append(model)
        return candidates


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

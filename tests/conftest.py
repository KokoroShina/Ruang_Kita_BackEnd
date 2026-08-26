"""Infrastruktur test Ruang Kita.

PENTING: env DATABASE_URL di-set SEBELUM import modul app apa pun,
karena engine SQLAlchemy dibangun saat import (app.db.session).

Test memakai database TERPISAH `ruang_kita_test_db` di server MySQL yang sama.
Data development (`ruang_kita_db`) tidak pernah tersentuh.

Semua AI di-mock (tests/fakes.py) -> deterministik, cepat, gratis, tanpa flaky rate limit.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ---- 1. Env override SEBELUM import app -----------------------------------
TEST_DB_NAME = "ruang_kita_test_db"
os.environ["DATABASE_URL"] = f"mysql+aiomysql://root@localhost:3306/{TEST_DB_NAME}"
os.environ["ENVIRONMENT"] = "testing"  # matikan SQL echo yang berisik

# ---- 2. Siapkan database-nya sendiri (sekali saat koleksi) ------------------
import pymysql  # noqa: E402

_conn = pymysql.connect(host="localhost", port=3306, user="root", charset="utf8mb4")
with _conn.cursor() as _cur:
    _cur.execute(
        f"CREATE DATABASE IF NOT EXISTS {TEST_DB_NAME} "
        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )
_conn.commit()
_conn.close()

# ---- 3. Import aplikasi (dengan env test aktif) -----------------------------
import httpx  # noqa: E402
import pytest  # noqa: E402

from main import app as _app  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import AsyncSessionLocal, engine  # noqa: E402
import app.models  # noqa: F401,E402  — pastikan semua model terdaftar di metadata

TABLES = list(reversed(Base.metadata.sorted_tables))

# Baseline konten psikoedukasi — dipulihkan setelah tiap truncate supaya
# browse/rekomendasi selalu punya bahan seperti kondisi nyata.
_CONTENT_SEED = (ROOT / "scripts" / "content_seed.json").read_text(encoding="utf-8")


async def _seed_content() -> None:
    import json
    from datetime import datetime, timezone as _tz

    from app.models.content_library import ContentLibrary

    rows = json.loads(_CONTENT_SEED)
    now = datetime.now(_tz.utc).replace(tzinfo=None)
    async with AsyncSessionLocal() as db:
        for row in rows:
            is_pub = bool(row.get("is_published"))
            db.add(
                ContentLibrary(
                    slug=row["slug"].lower(),
                    title=row["title"],
                    summary=row.get("summary"),
                    content_body=row.get("content_body"),
                    content_type=row.get("content_type", "article"),
                    topics=[t.lower() for t in row.get("topics", [])],
                    source_url=row.get("source_url"),
                    duration_minutes=row.get("duration_minutes"),
                    language=row.get("language", "id"),
                    is_published=is_pub,
                    published_at=now if is_pub else None,
                )
            )
        await db.commit()


@pytest.fixture(scope="session", autouse=True)
async def _schema():
    """Buat semua tabel sekali per sesi pytest."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
async def _clean_db(_schema):
    """Isolasi penuh antar test: truncate semua tabel + kembalikan seed baseline;
    setelah test, tunggu background task chat (auto-title) selesai agar tidak
    menulis ke tabel test berikutnya."""
    from sqlalchemy import text

    async with engine.begin() as conn:
        await conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for table in TABLES:
            await conn.execute(text(f"TRUNCATE TABLE `{table.name}`"))
        await conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    await _seed_content()
    yield

    import asyncio

    from app.services import chat_service

    pending = [t for t in list(chat_service._background_tasks) if not t.done()]
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=30) as c:
        yield c


@pytest.fixture
def make_user(client):
    """Factory: registrasi + login -> header Authorization siap pakai."""

    async def _make(email: str, password: str = "PasswordKuat#1") -> dict:
        r = await client.post(
            "/api/v1/auth/register", json={"email": email, "password": password}
        )
        assert r.status_code == 201, r.text
        r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _make


@pytest.fixture
def as_admin(make_user, monkeypatch):
    """User biasa yang emailnya didaftarkan sbg admin (restore otomatis pasca-test)."""

    async def _make(email: str = "admin@test.id", **kwargs) -> dict:
        headers = await make_user(email, **kwargs)
        monkeypatch.setattr(settings, "ADMIN_EMAILS", [email])
        return headers

    return _make

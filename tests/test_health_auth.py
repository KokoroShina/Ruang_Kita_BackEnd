"""Test endpoint dasar: health + auth (register/login/me)."""

import pytest


async def test_health_ok(client):
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] == "up"


async def test_register_success(client):
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": "Baru@Test.id", "password": "PasswordKuat#1", "full_name": "Budi"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == "baru@test.id"  # lowercase otomatis
    assert body["full_name"] == "Budi"
    assert body["is_active"] is True
    assert body["consent_version"] == "v1"
    assert "password" not in body and "hashed_password" not in body


async def test_register_duplicate_email_case_insensitive(client, make_user):
    await make_user("dup@test.id")
    r = await client.post(
        "/api/v1/auth/register", json={"email": "DUP@TEST.ID", "password": "PasswordKuat#1"}
    )
    assert r.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "pendek@test.id", "password": "abc"},          # password < 8
        {"email": "bukan-email", "password": "PasswordKuat#1"},  # email invalid
    ],
)
async def test_register_validation_errors(client, payload):
    r = await client.post("/api/v1/auth/register", json=payload)
    assert r.status_code == 422


async def test_login_wrong_password_generic_message(client, make_user):
    await make_user("login@test.id")
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@test.id", "password": "PasswordSalah#999"},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "Email atau password salah"


async def test_login_unknown_email_same_message(client):
    r = await client.post(
        "/api/v1/auth/login", json={"email": "tidakada@test.id", "password": "ApaPun#123"}
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "Email atau password salah"


async def test_login_inactive_account(client, make_user):
    headers = await make_user("nonaktif@test.id")
    # nonaktifkan via DB langsung
    from sqlalchemy import select, update

    from app.db.session import AsyncSessionLocal
    from app.models.user import User

    async with AsyncSessionLocal() as db:
        uid = (await db.execute(select(User.id).where(User.email == "nonaktif@test.id"))).scalar_one()
        await db.execute(update(User).where(User.id == uid).values(is_active=False))
        await db.commit()

    r = await client.post(
        "/api/v1/auth/login", json={"email": "nonaktif@test.id", "password": "PasswordKuat#1"}
    )
    assert r.status_code == 403
    # token lama pun ditolak
    r = await client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 401


async def test_me_with_token(client, make_user):
    headers = await make_user("me@test.id")
    r = await client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["email"] == "me@test.id"


async def test_me_without_token(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401


# ===== Flag is_admin (ADMIN_EMAILS) =====


async def test_login_regular_user_is_admin_false(client, make_user):
    await make_user("plain@test.id")
    r = await client.post(
        "/api/v1/auth/login", json={"email": "plain@test.id", "password": "PasswordKuat#1"}
    )
    assert r.status_code == 200
    assert r.json()["is_admin"] is False


async def test_login_admin_email_is_admin_true(client, make_user, monkeypatch):
    from app.core.config import settings

    email = "boss@test.id"
    await make_user(email)
    monkeypatch.setattr(settings, "ADMIN_EMAILS", [email])

    r = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "PasswordKuat#1"}
    )
    assert r.status_code == 200
    assert r.json()["is_admin"] is True


async def test_me_reports_is_admin(client, make_user, monkeypatch):
    from app.core.config import settings

    email = "adminme@test.id"
    headers = await make_user(email)
    # Admin ditunjuk SETELAH login — /me tetap harus melaporkan status terkini
    monkeypatch.setattr(settings, "ADMIN_EMAILS", [email])

    r = await client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["is_admin"] is True

"""Test akun & privasi: PATCH profil, ganti password, export data, hapus akun."""


async def test_patch_full_name(client, make_user):
    headers = await make_user("profil@test.id")
    r = await client.patch("/api/v1/auth/me", headers=headers, json={"full_name": "Nama Baru"})
    assert r.status_code == 200
    assert r.json()["full_name"] == "Nama Baru"


async def test_change_password_flow(client, make_user):
    headers = await make_user("pass@test.id", password="PasswordLama#1")

    # new_password tanpa current_password -> 422 (validator)
    r = await client.patch(
        "/api/v1/auth/me", headers=headers, json={"new_password": "PasswordBaru#2"}
    )
    assert r.status_code == 422

    # current_password salah -> 400
    r = await client.patch(
        "/api/v1/auth/me",
        headers=headers,
        json={"current_password": "BukanPassword#9", "new_password": "PasswordBaru#2"},
    )
    assert r.status_code == 400

    # benar -> 200, login pakai password baru
    r = await client.patch(
        "/api/v1/auth/me",
        headers=headers,
        json={"current_password": "PasswordLama#1", "new_password": "PasswordBaru#2"},
    )
    assert r.status_code == 200

    r = await client.post(
        "/api/v1/auth/login", json={"email": "pass@test.id", "password": "PasswordBaru#2"}
    )
    assert r.status_code == 200
    # password lama ditolak
    r = await client.post(
        "/api/v1/auth/login", json={"email": "pass@test.id", "password": "PasswordLama#1"}
    )
    assert r.status_code == 401


async def test_export_contains_all_user_data(client, make_user):
    from uuid import UUID

    headers = await make_user("export@test.id")

    jid = (
        await client.post(
            "/api/v1/journal/entries", headers=headers, json={"content": "isi jurnal export"}
        )
    ).json()["id"]
    mid = (
        await client.post(
            "/api/v1/mood/logs", headers=headers, json={"mood_score": 3, "mood_label": "biasa"}
        )
    ).json()["id"]
    sid = (await client.post("/api/v1/chat/sessions", headers=headers, json={})).json()["id"]

    r = await client.get("/api/v1/me/export", headers=headers)
    assert r.status_code == 200
    assert "attachment" in r.headers.get("content-disposition", "")

    dump = r.json()
    assert dump["profile"]["email"] == "export@test.id"
    assert len(dump["journal_entries"]) == 1
    assert dump["journal_entries"][0]["content"] == "isi jurnal export"
    assert len(dump["mood_logs"]) == 1 and dump["mood_logs"][0]["mood_score"] == 3
    assert len(dump["chat_sessions"]) == 1
    assert dump["exported_at"]
    # ID valid UUID
    for value in (jid, mid, sid, dump["profile"]["id"]):
        UUID(value)


async def test_delete_account_requires_correct_password(client, make_user):
    headers = await make_user("del@test.id")
    r = await client.request(
        "DELETE", "/api/v1/account", headers=headers, json={"password": "SalahTotal#1"}
    )
    assert r.status_code == 400
    # akun masih ada & token masih valid
    assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 200


async def test_delete_account_hard_delete_with_cascade(client, make_user):
    from uuid import UUID

    from sqlalchemy import func, select

    from app.db.session import AsyncSessionLocal
    from app.models.chat import ChatMessage, ChatSession
    from app.models.journal_entry import JournalEntry
    from app.models.mood_log import MoodLog
    from app.models.user import User

    headers = await make_user("hapus@test.id")

    jid = (
        await client.post("/api/v1/journal/entries", headers=headers, json={"content": "x"})
    ).json()["id"]
    mid = (
        await client.post("/api/v1/mood/logs", headers=headers, json={"mood_score": 4})
    ).json()["id"]
    sid = (await client.post("/api/v1/chat/sessions", headers=headers, json={})).json()["id"]
    # isi satu pesan biar cascade chat_messages ikut teruji (crisis path tanpa AI)
    await client.post(
        f"/api/v1/chat/sessions/{sid}/messages",
        headers=headers,
        json={"content": "pesan biasa sebelum hapus"},
    )

    r = await client.request(
        "DELETE", "/api/v1/account", headers=headers, json={"password": "PasswordKuat#1"}
    )
    assert r.status_code == 204

    # token langsung mati
    assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 401

    # CASCADE: semua data hilang total dari DB
    async with AsyncSessionLocal() as db:
        jc = await db.scalar(
            select(func.count())
            .select_from(JournalEntry)
            .where(JournalEntry.id == UUID(jid))
        )
        mc = await db.scalar(
            select(func.count()).select_from(MoodLog).where(MoodLog.id == UUID(mid))
        )
        sc = await db.scalar(
            select(func.count()).select_from(ChatSession).where(ChatSession.id == UUID(sid))
        )
        msgc = await db.scalar(
            select(func.count())
            .select_from(ChatMessage)
            .where(ChatMessage.session_id == UUID(sid))
        )
        uc = await db.scalar(
            select(func.count()).select_from(User).where(User.email == "hapus@test.id")
        )
    assert jc == 0 and mc == 0 and sc == 0 and msgc == 0 and uc == 0

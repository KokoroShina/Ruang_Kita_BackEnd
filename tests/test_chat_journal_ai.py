"""Test Pahami (chat) & Kenali (jurnal) dengan AI di-mock + jalur crisis asli.

Mocking targets:
- generate_text -> app.services.chat_service.generate_text / app.services.journal_service.generate_text
- stream_text   -> app.services.ai.router.stream_text (di-import lokal oleh chat_service)
"""

import json

from tests.fakes import RecordingFakeAI, fake_stream_text


# ---------------------------------------------------------------------------
# Chat - CRUD
# ---------------------------------------------------------------------------


async def _mk_session(client, h, title=None):
    r = await client.post("/api/v1/chat/sessions", headers=h, json={"title": title} if title else {})
    assert r.status_code == 201, r.text
    return r.json()


async def test_session_crud(client, make_user):
    h = await make_user("chat1@test.id")
    s = await _mk_session(client, h, "Judul Manual")

    r = await client.get("/api/v1/chat/sessions", headers=h)
    assert any(x["id"] == s["id"] for x in r.json())

    detail = await client.get(f"/api/v1/chat/sessions/{s['id']}", headers=h)
    assert detail.status_code == 200
    assert detail.json()["messages"] == []

    r = await client.delete(f"/api/v1/chat/sessions/{s['id']}", headers=h)
    assert r.status_code == 204
    assert (await client.get(f"/api/v1/chat/sessions/{s['id']}", headers=h)).status_code == 404


async def test_session_ownership_404(client, make_user):
    hA = await make_user("pemilik@test.id")
    hB = await make_user("penyusup@test.id")
    s = await _mk_session(client, hA)
    for path in (f"/api/v1/chat/sessions/{s['id']}",):
        r = await client.get(path, headers=hB)
        assert r.status_code == 404
        r = await client.delete(path, headers=hB)
        assert r.status_code == 404


async def test_send_message_with_mocked_ai(client, make_user, monkeypatch):
    fake = RecordingFakeAI(reply="Aku mengerti perasaanmu. (fake)")
    monkeypatch.setattr("app.services.chat_service.generate_text", fake)

    h = await make_user("chat2@test.id")
    s = await _mk_session(client, h)

    # pesan 1 -> memicu auto-title background (dari hasil fake yang sama)
    r = await client.post(
        f"/api/v1/chat/sessions/{s['id']}/messages",
        headers=h,
        json={"content": "Aku lagi stres kuliah"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["crisis_detected"] is False
    assert body["assistant_message"]["content"] == "Aku mengerti perasaanmu. (fake)"
    assert body["assistant_message"]["provider"] == "fake-model:test"
    assert body["model_used"] == "fake-model:test"

    # Jeda antar giliran: timer MySQL di Windows kasar (~15ms); AI palsu instan bisa
    # membuat timestamp identik. AI asli butuh detik — jeda ini meniru ritme nyata.
    import asyncio

    await asyncio.sleep(0.06)

    # multi-turn: panggilan kedua harus membawa riwayat pesan pertama
    r = await client.post(
        f"/api/v1/chat/sessions/{s['id']}/messages",
        headers=h,
        json={"content": "Tadi aku bilang apa?"},
    )
    assert r.status_code == 200
    roles_contents = [(m["role"], m["content"]) for m in fake.last_messages]
    assert any(role == "user" and "stres kuliah" in c for role, c in roles_contents), (
        "riwayat multi-turn harus ikut ke LLM"
    )

    # urutan pesan di detail bergantian user/assistant
    detail = await client.get(f"/api/v1/chat/sessions/{s['id']}", headers=h)
    msgs = detail.json()["messages"]
    assert [m["sender_role"] for m in msgs] == ["user", "assistant", "user", "assistant"]

    # auto-title: background task — poll sampai judul muncul (maks ~10 detik)
    import asyncio

    title = None
    for _ in range(100):
        sessions = (await client.get("/api/v1/chat/sessions", headers=h)).json()
        target = next(x for x in sessions if x["id"] == s["id"])
        if target["title"]:
            title = target["title"]
            break
        await asyncio.sleep(0.1)
    assert title is not None, "auto-title tidak muncul dalam 10s"

    # manual title tidak pernah dioverride: fake dipakai lagi di sesi kedua
    s2 = await _mk_session(client, h, "Judul Manual Saya")
    await client.post(f"/api/v1/chat/sessions/{s2['id']}/messages", headers=h, json={"content": "halo lagi"})
    sessions = (await client.get("/api/v1/chat/sessions", headers=h)).json()
    target2 = next(x for x in sessions if x["id"] == s2["id"])
    assert target2["title"] == "Judul Manual Saya"


async def test_send_message_ai_failure_503_but_message_saved(client, make_user, monkeypatch):
    from app.services.ai.router import AIGatewayError

    async def failing(*args, **kwargs):
        raise AIGatewayError("Semua model gagal")

    monkeypatch.setattr("app.services.chat_service.generate_text", failing)

    h = await make_user("chat3@test.id")
    s = await _mk_session(client, h)

    r = await client.post(
        f"/api/v1/chat/sessions/{s['id']}/messages", headers=h, json={"content": "halo"}
    )
    assert r.status_code == 503

    detail = await client.get(f"/api/v1/chat/sessions/{s['id']}", headers=h)
    msgs = detail.json()["messages"]
    assert [m["sender_role"] for m in msgs] == ["user"], "pesan user tetap tersimpan"


async def test_chat_crisis_input_no_ai_called(client, make_user, monkeypatch):
    fake = RecordingFakeAI()
    monkeypatch.setattr("app.services.chat_service.generate_text", fake)

    h = await make_user("chat4@test.id")
    s = await _mk_session(client, h)

    r = await client.post(
        f"/api/v1/chat/sessions/{s['id']}/messages",
        headers=h,
        json={"content": "Aku capek banget sampai mikir pengen mati aja."},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["crisis_detected"] is True
    assert "119" in body["assistant_message"]["content"]
    assert fake.called is False, "AI tidak boleh dipanggil saat crisis input"

    detail = await client.get(f"/api/v1/chat/sessions/{s['id']}", headers=h)
    d = detail.json()
    assert d["crisis_flagged"] is True
    flagged_roles = [m["sender_role"] for m in d["messages"] if m["crisis_flagged"]]
    assert "user" in flagged_roles and "assistant" in flagged_roles


def _parse_sse(raw_text):
    """Parse SSE text -> list of {event, data}."""
    events = []
    current_event = None
    for line in raw_text.split("\n"):
        if line.startswith("event: "):
            current_event = line[7:].strip()
        elif line.startswith("data: ") and current_event:
            events.append({"event": current_event, "data": json.loads(line[6:])})
            current_event = None
    return events


async def test_streaming_sse_normal_flow(client, make_user, monkeypatch):
    monkeypatch.setattr(
        "app.services.ai.router.stream_text",
        fake_stream_text("Halo ", "teman, ", "tarik napas ya."),
    )

    h = await make_user("chat5@test.id")
    s = await _mk_session(client, h)

    async with client.stream(
        "POST",
        f"/api/v1/chat/sessions/{s['id']}/messages/stream",
        headers=h,
        json={"content": "kasih tips tenang dong"},
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        raw = "".join([chunk async for chunk in resp.aiter_text()])

    events = _parse_sse(raw)
    kinds = [e["event"] for e in events]
    assert kinds[0] == "meta"
    assert kinds.count("delta") >= 3

    assembled = "".join(e["data"]["text"] for e in events if e["event"] == "delta")
    assert assembled == "Halo teman, tarik napas ya.\n\n_(Catatan: aku teman refleksi, bukan pengganti psikolog atau psikiater. Kalau bebanmu terasa terlalu berat, ngobrol sama tenaga profesional itu langkah yang berani.)_"
    assert "(Catatan:" in assembled  # disclaimer selalu delta terakhir

    done_evt = next(e for e in events if e["event"] == "done")
    assert done_evt["data"]["crisis_detected"] is False
    assert done_evt["data"]["model_used"] == "fake-model:test"

    # balasan utuh tersimpan di DB
    detail = await client.get(f"/api/v1/chat/sessions/{s['id']}", headers=h)
    assistant = [m for m in detail.json()["messages"] if m["sender_role"] == "assistant"]
    assert len(assistant) == 1 and assistant[0]["content"] == assembled


async def test_streaming_crisis_input_path(client, make_user, monkeypatch):
    fake_stream = fake_stream_text()  # takkan pernah dipakai
    monkeypatch.setattr("app.services.ai.router.stream_text", fake_stream)

    h = await make_user("chat6@test.id")
    s = await _mk_session(client, h)

    async with client.stream(
        "POST",
        f"/api/v1/chat/sessions/{s['id']}/messages/stream",
        headers=h,
        json={"content": "pengen mati aja rasanya"},
    ) as resp:
        raw = "".join([chunk async for chunk in resp.aiter_text()])

    events = _parse_sse(raw)
    kinds = [e["event"] for e in events]
    assert kinds == ["meta", "delta", "done"]  # kontrak crisis input: tanpa AI
    delta = next(e for e in events if e["event"] == "delta")
    assert "119" in delta["data"]["text"]
    done_evt = next(e for e in events if e["event"] == "done")
    assert done_evt["data"]["crisis_detected"] is True


async def test_streaming_output_crisis_midstream_replaces_partial(client, make_user, monkeypatch):
    monkeypatch.setattr(
        "app.services.ai.router.stream_text",
        fake_stream_text("partial aman ", "lanjutan teks ", crisis_at=2),
    )

    h = await make_user("chat7@test.id")
    s = await _mk_session(client, h)

    async with client.stream(
        "POST",
        f"/api/v1/chat/sessions/{s['id']}/messages/stream",
        headers=h,
        json={"content": "ceritakan sesuatu"},
    ) as resp:
        raw = "".join([chunk async for chunk in resp.aiter_text()])

    events = _parse_sse(raw)
    kinds = [e["event"] for e in events]
    assert "crisis" in kinds
    assert kinds[-1] == "done"
    done_evt = next(e for e in events if e["event"] == "done")
    assert done_evt["data"]["crisis_detected"] is True

    # partial dibuang; yang tersimpan hanya balasan dukungan
    detail = await client.get(f"/api/v1/chat/sessions/{s['id']}", headers=h)
    assistants = [m for m in detail.json()["messages"] if m["sender_role"] == "assistant"]
    assert len(assistants) == 1
    assert "119" in assistants[0]["content"]
    assert "partial" not in assistants[0]["content"]
    assert assistants[0]["crisis_flagged"] is True
    assert detail.json()["crisis_flagged"] is True


# ---------------------------------------------------------------------------
# Journal - CRUD + analyze (mocked AI) + crisis
# ---------------------------------------------------------------------------


async def _mk_entry(client, h, content="Isi jurnal biasa.", title=None):
    payload = {"content": content}
    if title:
        payload["title"] = title
    r = await client.post("/api/v1/journal/entries", headers=h, json=payload)
    assert r.status_code == 201, r.text
    return r.json()


async def test_journal_crud_and_stale_insight(client, make_user):
    h = await make_user("jrn1@test.id")
    entry = await _mk_entry(client, h, "Catatan hari ini.", "Judul Jurnal")

    eid = entry["id"]
    assert entry["ai_insight"] is None

    r = await client.get("/api/v1/journal/entries", headers=h)
    assert any(x["id"] == eid for x in r.json())

    # update konten saja -> insight tetap null, judul utuh
    r = await client.put(
        f"/api/v1/journal/entries/{eid}", headers=h, json={"content": "Konten baru."}
    )
    assert r.status_code == 200 and r.json()["ai_insight"] is None
    assert r.json()["title"] == "Judul Jurnal"

    r = await client.delete(f"/api/v1/journal/entries/{eid}", headers=h)
    assert r.status_code == 204
    assert (await client.get(f"/api/v1/journal/entries/{eid}", headers=h)).status_code == 404


async def test_journal_ownership_404(client, make_user):
    hA = await make_user("jpemilik@test.id")
    hB = await make_user("jlain@test.id")
    e = await _mk_entry(client, hA)
    for method in ("get", "put", "delete"):
        kwargs = {"headers": hB}
        if method == "put":
            kwargs["json"] = {"content": "hack"}
        r = await getattr(client, method)(f"/api/v1/journal/entries/{e['id']}", **kwargs)
        assert r.status_code == 404


async def test_journal_analyze_with_mocked_ai(client, make_user, monkeypatch):
    fake = RecordingFakeAI(reply="Refleksi palsu: kamu sudah berani menulis.")
    monkeypatch.setattr("app.services.journal_service.generate_text", fake)

    h = await make_user("jrn2@test.id")
    e = await _mk_entry(client, h, "Hari ini cukup berat tapi aku bertahan.")

    r = await client.post(f"/api/v1/journal/entries/{e['id']}/analyze", headers=h, json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["crisis_detected"] is False
    assert body["entry"]["ai_insight"] == "Refleksi palsu: kamu sudah berani menulis."
    assert body["model_used"] == "fake-model:test"
    assert fake.calls[0]["endpoint_type"] == "journal_analysis"


async def test_journal_analyze_crisis_no_ai(client, make_user, monkeypatch):
    fake = RecordingFakeAI()
    monkeypatch.setattr("app.services.journal_service.generate_text", fake)

    h = await make_user("jrn3@test.id")
    e = await _mk_entry(client, h, "Aku nggak sanggup lagi, mulai kepikiran bunuh diri.")

    r = await client.post(f"/api/v1/journal/entries/{e['id']}/analyze", headers=h, json={})
    assert r.status_code == 200
    body = r.json()
    assert body["crisis_detected"] is True
    assert "119" in body["entry"]["ai_insight"]
    assert body["entry"]["crisis_flagged"] is True
    assert fake.called is False


async def test_journal_analyze_not_found_other_user(client, make_user):
    hA = await make_user("ja@test.id")
    hB = await make_user("jb@test.id")
    e = await _mk_entry(client, hA)
    r = await client.post(f"/api/v1/journal/entries/{e['id']}/analyze", headers=hB, json={})
    assert r.status_code == 404

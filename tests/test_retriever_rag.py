"""Test RAG Fase 1: retrieval leksikal + wiring ke chat & jurnal.

Semua AI di-mock — yang diuji adalah LOGIKA retrieval dan kontrak respons/event.
"""

from tests.fakes import RecordingFakeAI, fake_stream_text


async def _publish_topic(client, admin_h, slug, name, alt=None):
    r = await client.post(
        "/api/v1/admin/topics",
        headers=admin_h,
        json={
            "slug": slug,
            "name": name,
            "category": "trauma" if "ptsd" in slug else "anxiety",
            "summary": f"Ringkasan {name} untuk grounding.",
            **({"alt_names": alt} if alt else {}),
            "signs_symptoms": ["gejala satu", "gejala dua", "gejala tiga"],
            "when_to_seek_help": "Bila gangguan aktivitas harian.",
            "is_published": True,
        },
    )
    assert r.status_code == 201, r.text


# ---------------------------------------------------------------------------
# Unit retrieval
# ---------------------------------------------------------------------------


async def test_retriever_matches_slug_alt_names_and_ignores_draft(
    client, as_admin
):
    from sqlalchemy import select

    from app.db.session import AsyncSessionLocal
    from app.services.ai.retriever import retrieve_context

    admin_h = await as_admin("rag-admin@test.id")

    await _publish_topic(client, admin_h, "ptsd", "PTSD", alt=["gangguan stres pascatrauma"])
    # draft: slug disebut tapi TIDAK boleh diambil
    await client.post(
        "/api/v1/admin/topics",
        headers=admin_h,
        json={"slug": "draft-rahasia", "name": "Draft Rahasia", "summary": "s"},
    )

    async with AsyncSessionLocal() as db:
        res = await retrieve_context(db, "Kayaknya gejalaku mirip ptsd deh...")
    assert res.topic_slugs == ["ptsd"]
    assert len(res.snippets) == 1
    assert "[Topik: PTSD]" in res.snippets[0]
    assert "/topics/ptsd" in res.snippets[0]

    async with AsyncSessionLocal() as db:
        res2 = await retrieve_context(db, "aku baca soal draft-rahasia")
    assert res2.topic_slugs == [] and not res2.has_context

    async with AsyncSessionLocal() as db:
        res3 = await retrieve_context(db, "")
    assert not res3.has_context


# ---------------------------------------------------------------------------
# Chat non-streaming
# ---------------------------------------------------------------------------


async def test_chat_send_grounded_when_topic_mentioned(client, make_user, as_admin, monkeypatch):
    fake = RecordingFakeAI(reply="Aku dengar kamu. Tentang itu ada bacaan bagus lho.")
    monkeypatch.setattr("app.services.chat_service.generate_text", fake)
    admin_h = await as_admin("rag-chat@test.id")
    h = await make_user("rag-user@test.id")
    await _publish_topic(client, admin_h, "ptsd", "PTSD")

    s = (
        await client.post("/api/v1/chat/sessions", headers=h, json={})
    ).json()
    r = await client.post(
        f"/api/v1/chat/sessions/{s['id']}/messages",
        headers=h,
        json={"content": "Kayaknya gejalaku mirip ptsd ya..."},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["grounded_topics"] == ["ptsd"]
    # blok konteks benar-benar sampai ke LLM (panggilan PERTAMA = chat;
    # panggilan berikutnya adalah auto-title background yang memakai fake yang sama)
    system_msg = fake.calls[0]["messages"][0]["content"]
    assert "[Topik: PTSD]" in system_msg
    assert "Aturan pakai referensi" in system_msg


async def test_chat_send_no_mention_no_grounding(client, make_user, as_admin, monkeypatch):
    fake = RecordingFakeAI()
    monkeypatch.setattr("app.services.chat_service.generate_text", fake)
    await as_admin("rag-chat2@test.id")
    h = await make_user("rag-user2@test.id")

    s = (await client.post("/api/v1/chat/sessions", headers=h, json={})).json()
    r = await client.post(
        f"/api/v1/chat/sessions/{s['id']}/messages",
        headers=h,
        json={"content": "hari ini biasa aja sih"},
    )
    body = r.json()
    assert body["grounded_topics"] == []
    assert "[Topik:" not in fake.last_messages[0]["content"]


# ---------------------------------------------------------------------------
# Chat streaming (SSE)
# ---------------------------------------------------------------------------


def _parse_sse(raw):
    events, cur = [], None
    for line in raw.split("\n"):
        if line.startswith("event: "):
            cur = line[7:].strip()
        elif line.startswith("data: ") and cur:
            import json

            events.append({"event": cur, "data": json.loads(line[6:])})
            cur = None
    return events


async def test_stream_emits_grounded_event_before_deltas(client, make_user, as_admin, monkeypatch):
    monkeypatch.setattr(
        "app.services.ai.router.stream_text",
        fake_stream_text("Tentang ", "itu, ", "coba baca ya."),
    )
    admin_h = await as_admin("rag-stream@test.id")
    h = await make_user("rag-user3@test.id")
    await _publish_topic(client, admin_h, "ptsd", "PTSD")

    s = (await client.post("/api/v1/chat/sessions", headers=h, json={})).json()
    async with client.stream(
        "POST",
        f"/api/v1/chat/sessions/{s['id']}/messages/stream",
        headers=h,
        json={"content": "kayaknya aku ptsd nih"},
    ) as resp:
        raw = "".join([chunk async for chunk in resp.aiter_text()])

    events = _parse_sse(raw)
    kinds = [e["event"] for e in events]
    grounded_idx = kinds.index("grounded")
    first_delta_idx = kinds.index("delta")
    assert grounded_idx < first_delta_idx  # sebelum delta pertama
    assert events[grounded_idx]["data"]["topics"] == ["ptsd"]
    done_evt = next(e for e in events if e["event"] == "done")
    assert done_evt["data"]["grounded_topics"] == ["ptsd"]


async def test_stream_crisis_path_has_no_grounding_event(client, make_user, monkeypatch):
    monkeypatch.setattr("app.services.ai.router.stream_text", fake_stream_text())
    h = await make_user("rag-crisis@test.id")
    s = (await client.post("/api/v1/chat/sessions", headers=h, json={})).json()

    async with client.stream(
        "POST",
        f"/api/v1/chat/sessions/{s['id']}/messages/stream",
        headers=h,
        json={"content": "pengen mati aja rasanya"},  # crisis: retriever tidak boleh jalan
    ) as resp:
        raw = "".join([chunk async for chunk in resp.aiter_text()])

    kinds = [e["event"] for e in _parse_sse(raw)]
    assert kinds == ["meta", "delta", "done"]  # tanpa grounded — jalur safety bersih


# ---------------------------------------------------------------------------
# Journal analyze
# ---------------------------------------------------------------------------


async def test_journal_analyze_grounded(client, make_user, as_admin, monkeypatch):
    fake = RecordingFakeAI(reply="Refleksi dengan pemahaman topik.")
    monkeypatch.setattr("app.services.journal_service.generate_text", fake)
    admin_h = await as_admin("rag-jrn@test.id")
    h = await make_user("rag-jrn-user@test.id")
    await _publish_topic(client, admin_h, "ptsd", "PTSD", alt=["stres pascatrauma"])

    e = (
        await client.post(
            "/api/v1/journal/entries",
            headers=h,
            json={"content": "Setelah kejadian itu aku sering kilas balik, kayak gejala stres pascatrauma."},
        )
    ).json()

    r = await client.post(f"/api/v1/journal/entries/{e['id']}/analyze", headers=h, json={})
    assert r.status_code == 200
    body = r.json()
    assert body["grounded_topics"] == ["ptsd"]
    assert body["crisis_detected"] is False
    assert "[Topik: PTSD]" in fake.calls[0]["messages"][0]["content"]


async def test_journal_analyze_crisis_skips_retrieval(client, make_user, as_admin, monkeypatch):
    fake = RecordingFakeAI()
    monkeypatch.setattr("app.services.journal_service.generate_text", fake)
    admin_h = await as_admin("rag-jrn2@test.id")
    h = await make_user("rag-jrn-user2@test.id")
    await _publish_topic(client, admin_h, "ptsd", "PTSD")

    e = (
        await client.post(
            "/api/v1/journal/entries",
            headers=h,
            json={"content": "Aku kepikiran bunuh diri terus belakangan ini soal ptsd yang kubaca."},
        )
    ).json()

    r = await client.post(f"/api/v1/journal/entries/{e['id']}/analyze", headers=h, json={})
    body = r.json()
    assert body["crisis_detected"] is True
    assert body["grounded_topics"] == []  # crisis path: tanpa grounding
    assert fake.called is False

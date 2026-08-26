"""Test RAG Fase 2: retrieval SEMANTIK via embeddings — semua di-mock, tanpa API sungguhan."""

import pytest

from app.services.ai import embeddings as emb
from app.services.ai.retriever import retrieve_context


# ---------------------------------------------------------------------------
# Unit dasar
# ---------------------------------------------------------------------------


def test_cosine_identical_and_orthogonal():
    assert emb.cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert emb.cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert emb.cosine([], []) == 0.0
    assert emb.cosine([1.0], [1.0, 2.0]) == 0.0  # dimensi beda -> aman


async def test_embed_text_returns_none_when_disabled(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.GEMINI_API_KEY", None)
    assert await emb.embed_text("halo dunia") is None


# ---------------------------------------------------------------------------
# Retrieval semantik menangkap parafrase
# ---------------------------------------------------------------------------


async def _publish_with_vector(client, admin_h, slug, name, vector):
    """Publish topik lewat API, lalu tulis vektor langsung ke DB (tanpa panggil Gemini)."""
    r = await client.post(
        "/api/v1/admin/topics",
        headers=admin_h,
        json={
            "slug": slug,
            "name": name,
            "category": "trauma",
            "summary": f"Ringkasan {name}.",
            "is_published": True,
        },
    )
    assert r.status_code == 201, r.text

    from sqlalchemy import update

    from app.db.session import AsyncSessionLocal
    from app.models.mental_health_topic import MentalHealthTopic

    async with AsyncSessionLocal() as db:
        await db.execute(
            update(MentalHealthTopic)
            .where(MentalHealthTopic.slug == slug)
            .values(embedding=vector, embedded_at=__import__("datetime").datetime(2026, 1, 1))
        )
        await db.commit()


async def test_semantic_pass_catches_paraphrase(client, make_user, as_admin, monkeypatch):
    admin_h = await as_admin("sem-admin@test.id")
    await _publish_with_vector(client, admin_h, "ptsd", "PTSD", vector=[0.99, 0.1])

    # query vektor mirip -> cosine ~0.999 >= threshold
    async def fake_embed(text):
        return [1.0, 0.08]

    monkeypatch.setattr(emb, "embed_text", fake_embed)
    monkeypatch.setattr("app.core.config.settings.GEMINI_API_KEY", "fake-key")

    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        res = await retrieve_context(db, "terus teringat kejadian buruk yang lalu")  # tanpa kata 'ptsd'!
    assert res.topic_slugs == ["ptsd"]
    assert "[Topik: PTSD]" in res.snippets[0]
    assert "/topics/ptsd" in res.snippets[0]


async def test_semantic_below_threshold_excluded(client, make_user, as_admin, monkeypatch):
    admin_h = await as_admin("sem-admin2@test.id")
    await _publish_with_vector(client, admin_h, "ptsd", "PTSD", vector=[1.0, 0.0])

    async def fake_embed(text):
        return [0.0, 1.0]  # ortogonal -> cosine 0

    monkeypatch.setattr(emb, "embed_text", fake_embed)
    monkeypatch.setattr("app.core.config.settings.GEMINI_API_KEY", "fake-key")

    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        res = await retrieve_context(db, "cerita yang sama sekali tidak berkaitan")
    assert res.topic_slugs == []


async def test_semantic_error_falls_back_to_lexical_only(client, make_user, as_admin, monkeypatch):
    admin_h = await as_admin("sem-admin3@test.id")
    await _publish_with_vector(client, admin_h, "gad", "GAD", vector=[0.5, 0.5])

    async def broken_embed(text):
        raise RuntimeError("API down")

    monkeypatch.setattr(emb, "embed_text", broken_embed)
    monkeypatch.setattr("app.core.config.settings.GEMINI_API_KEY", "fake-key")

    from app.db.session import AsyncSessionLocal

    # leksikal tetap bekerja untuk penyebutan eksplisit...
    async with AsyncSessionLocal() as db:
        res = await retrieve_context(db, "aku baca soal gad tadi")
    assert res.topic_slugs == ["gad"]

    # ...dan tanpa penyebutan, hasil kosong TANPA exception
    async with AsyncSessionLocal() as db:
        res2 = await retrieve_context(db, "teks acak tanpa kecocokan")
    assert res2.topic_slugs == []


# ---------------------------------------------------------------------------
# Auto-embed saat publish (admin)
# ---------------------------------------------------------------------------


async def test_admin_publish_stores_embedding(client, as_admin, monkeypatch):
    captured: dict = {}

    async def fake_embed(text):
        captured["text"] = text
        return [0.42, 0.42]

    monkeypatch.setattr(emb, "embed_text", fake_embed)
    monkeypatch.setattr("app.core.config.settings.GEMINI_API_KEY", "fake-key")
    admin_h = await as_admin("sem-pub@test.id")

    r = await client.post(
        "/api/v1/admin/topics",
        headers=admin_h,
        json={"slug": "embed-uji", "name": "Embed Uji", "summary": "uji auto-embed", "is_published": True},
    )
    assert r.status_code == 201

    # vektor TIDAK diekspos di respons API (internal) — verifikasi via DB
    from sqlalchemy import select

    from app.db.session import AsyncSessionLocal
    from app.models.mental_health_topic import MentalHealthTopic

    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(
                select(MentalHealthTopic.embedding, MentalHealthTopic.embedded_at).where(
                    MentalHealthTopic.slug == "embed-uji"
                )
            )
        ).one()
    assert row[0] == [0.42, 0.42]
    assert row[1] is not None
    assert "Embed Uji" in captured["text"]

    # publish ulang -> vektor diperbarui
    await client.patch("/api/v1/admin/topics/embed-uji", headers=admin_h, json={"is_published": False})
    await client.patch("/api/v1/admin/topics/embed-uji", headers=admin_h, json={"is_published": True})

    from datetime import datetime

    async with AsyncSessionLocal() as db:
        emb2 = await db.scalar(
            select(MentalHealthTopic.embedding).where(MentalHealthTopic.slug == "embed-uji")
        )
    assert emb2 == [0.42, 0.42]


async def test_publish_without_key_stores_no_embedding(client, as_admin):
    admin_h = await as_admin("sem-nok@test.id")  # GEMINI_API_KEY kosong (default env test)

    r = await client.post(
        "/api/v1/admin/topics",
        headers=admin_h,
        json={"slug": "no-key-uji", "name": "No Key", "summary": "s", "is_published": True},
    )
    assert r.status_code == 201

    from sqlalchemy import select

    from app.db.session import AsyncSessionLocal
    from app.models.mental_health_topic import MentalHealthTopic

    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(
                select(MentalHealthTopic.embedding, MentalHealthTopic.embedded_at).where(
                    MentalHealthTopic.slug == "no-key-uji"
                )
            )
        ).one()
    assert row[0] is None and row[1] is None

"""Test Temukan: browse konten, admin content CRUD, rekomendasi rule-based."""


async def _publish_topic(client, admin_h, slug, name, category, alt=None):
    r = await client.post(
        "/api/v1/admin/topics",
        headers=admin_h,
        json={
            "slug": slug, "name": name, "category": category,
            "summary": f"Ringkasan {name}.",
            **({"alt_names": alt} if alt else {}),
            "is_published": True,
        },
    )
    assert r.status_code == 201, r.text


async def test_browse_content_published_only_and_filters(client, make_user):
    h = await make_user("browse@test.id")

    r = await client.get("/api/v1/content", headers=h)
    items = r.json()
    assert len(items) == 5  # seed 5 konten published
    assert all(i["is_published"] for i in items)

    r = await client.get("/api/v1/content", params={"content_type": "exercise"}, headers=h)
    assert len(r.json()) == 4

    r = await client.get("/api/v1/content", params={"topic": "anxiety"}, headers=h)
    assert len(r.json()) == 4

    r = await client.get("/api/v1/content", params={"q": "overthinking"}, headers=h)
    assert [i["slug"] for i in r.json()] == ["mengenali-pemicu-overthinking"]


async def test_admin_content_crud_lifecycle(client, make_user, as_admin):
    admin_h = await as_admin("admin-konten@test.id")
    hB = await make_user("warga@test.id")

    # non-admin ditolak
    r = await client.post(
        "/api/v1/admin/content", headers=hB,
        json={"slug": "ilegal", "title": "I", "summary": "s"},
    )
    assert r.status_code == 403

    # create draft -> hidden dari publik
    r = await client.post(
        "/api/v1/admin/content",
        headers=admin_h,
        json={"slug": "Konten-Uji", "title": "Konten Uji", "summary": "uji", "topics": ["mood"]},
    )
    assert r.status_code == 201
    assert r.json()["slug"] == "konten-uji"
    assert all(i["slug"] != "konten-uji" for i in (await client.get("/api/v1/content", headers=hB)).json())

    # publish -> visible
    r = await client.patch(
        "/api/v1/admin/content/konten-uji", headers=admin_h, json={"is_published": True}
    )
    assert r.status_code == 200 and r.json()["published_at"]
    assert any(i["slug"] == "konten-uji" for i in (await client.get("/api/v1/content", headers=hB)).json())

    # duplikat slug -> 409; patch kosong -> 422
    r = await client.post(
        "/api/v1/admin/content", headers=admin_h,
        json={"slug": "konten-uji", "title": "D", "summary": "d"},
    )
    assert r.status_code == 409
    r = await client.patch("/api/v1/admin/content/konten-uji", headers=admin_h, json={})
    assert r.status_code == 422

    # delete -> hilang
    r = await client.delete("/api/v1/admin/content/konten-uji", headers=admin_h)
    assert r.status_code == 204
    assert all(i["slug"] != "konten-uji" for i in (await client.get("/api/v1/content", headers=hB)).json())


async def test_recommendations_fresh_user_fallback(client, make_user):
    h = await make_user("fresh@test.id")
    r = await client.get("/api/v1/discover/recommendations", headers=h)
    rec = r.json()
    assert rec["topics"] == []
    assert len(rec["content"]) >= 1
    assert all(c["matched_topics"] == [] for c in rec["content"])
    assert any("umum" in b.lower() for b in rec["based_on"])


async def test_recommendations_personal_signals(client, make_user, as_admin):
    admin_h = await as_admin("rec-admin@test.id")
    h = await make_user("personal@test.id")

    await _publish_topic(client, admin_h, "ptsd", "PTSD Uji", "trauma")
    await _publish_topic(client, admin_h, "gad-uji2", "GAD Uji Dua", "anxiety")

    # sinyal 1: jurnal menyebut 'ptsd' -> skor tertinggi
    r = await client.post(
        "/api/v1/journal/entries",
        headers=h,
        json={"content": "Kayaknya gejalaku mirip ptsd yang dulu aku baca. Setiap ingat trauma itu badanku gemetar."},
    )
    assert r.status_code == 201

    # sinyal 2: mood label 'cemas' -> kategori anxiety
    r = await client.post(
        "/api/v1/mood/logs", headers=h, json={"mood_score": 2, "mood_label": "cemas banget"}
    )
    assert r.status_code == 201

    r = await client.get("/api/v1/discover/recommendations", headers=h)
    rec = r.json()
    slugs = [t["slug"] for t in rec["topics"]]

    assert "ptsd" in slugs
    ptsd = next(t for t in rec["topics"] if t["slug"] == "ptsd")
    assert any(x["kind"] == "journal_topic_match" for x in ptsd["reasons"])

    assert "gad-uji2" in slugs
    gad = next(t for t in rec["topics"] if t["slug"] == "gad-uji2")
    assert any(x["kind"] == "mood_label" for x in gad["reasons"])

    ptsd_score = next(t["score"] for t in rec["topics"] if t["slug"] == "ptsd")
    gad_score = next(t["score"] for t in rec["topics"] if t["slug"] == "gad-uji2")
    assert ptsd_score > gad_score

    assert any("jurnal" in b.lower() for b in rec["based_on"])

    matched = [c for c in rec["content"] if c["matched_topics"]]
    assert len(matched) >= 2


async def test_recommendations_low_mood_trend_signal(client, make_user, as_admin):
    admin_h = await as_admin("low-admin@test.id")
    h = await make_user("lowmood@test.id")
    await _publish_topic(client, admin_h, "depresi-low", "Depresi Low", "mood")

    for _ in range(4):
        await client.post("/api/v1/mood/logs", headers=h, json={"mood_score": 1})

    r = await client.get("/api/v1/discover/recommendations", headers=h)
    rec = r.json()
    dep = next((t for t in rec["topics"] if t["slug"] == "depresi-low"), None)
    assert dep is not None
    assert any(x["kind"] == "low_mood_trend" for x in dep["reasons"])

"""Test ensiklopedia: admin gate, CRUD, publish lifecycle, search/filter."""


async def test_admin_gate_empty_always_403(client, make_user):
    h = await make_user("siapa@test.id")
    r = await client.post(
        "/api/v1/admin/topics",
        headers=h,
        json={"slug": "uji", "name": "Uji", "summary": "s"},
    )
    assert r.status_code == 403  # ADMIN_EMAILS kosong -> user mana pun ditolak


async def test_non_admin_403(client, make_user, as_admin):
    await as_admin("bos@test.id")
    hB = await make_user("orang@test.id")
    r = await client.post(
        "/api/v1/admin/topics",
        headers=hB,
        json={"slug": "uji-b", "name": "B", "summary": "s"},
    )
    assert r.status_code == 403


async def test_create_draft_slug_normalized_and_hidden(client, as_admin):
    headers = await as_admin()
    r = await client.post(
        "/api/v1/admin/topics",
        headers=headers,
        json={
            "slug": "Topik-Uji-Draft",
            "name": "Topik Uji Draft",
            "alt_names": ["nama populer uji"],
            "category": "mood",
            "summary": "Ringkasan topik draft untuk pengujian.",
            "signs_symptoms": ["gejala satu"],
            "myths_facts": [{"myth": "m", "fact": "f"}],
            "support_resources": [{"name": "SEJIWA", "contact": "119 ext. 8"}],
            "related_topic_slugs": [],
            "is_published": False,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["slug"] == "topik-uji-draft"  # lowercase otomatis
    assert body["is_published"] is False and body["published_at"] is None

    # draft tersembunyi dari publik (list + detail)
    r = await client.get("/api/v1/topics", headers=headers)
    assert all(t["slug"] != "topik-uji-draft" for t in r.json())
    r = await client.get("/api/v1/topics/topik-uji-draft", headers=headers)
    assert r.status_code == 404


async def test_duplicate_slug_409_and_invalid_slug_422(client, as_admin):
    headers = await as_admin()
    payload = {"slug": "dobel-slug", "name": "N", "summary": "s"}
    assert (await client.post("/api/v1/admin/topics", headers=headers, json=payload)).status_code == 201

    r = await client.post(
        "/api/v1/admin/topics", headers=headers, json={"slug": "Dobel-Slug", "name": "D", "summary": "d"}
    )
    assert r.status_code == 409

    r = await client.post(
        "/api/v1/admin/topics", headers=headers, json={"slug": "ada spasi!", "name": "N", "summary": "s"}
    )
    assert r.status_code == 422


async def test_publish_lifecycle(client, as_admin):
    headers = await as_admin()
    slug = "lifecycle-uji"
    await client.post(
        "/api/v1/admin/topics",
        headers=headers,
        json={"slug": slug, "name": "Lifecycle", "summary": "uji publish"},
    )

    # PATCH publish -> published_at terisi & muncul publik
    r = await client.patch(f"/api/v1/admin/topics/{slug}", headers=headers, json={"is_published": True})
    assert r.status_code == 200
    assert r.json()["published_at"] is not None
    assert any(t["slug"] == slug for t in (await client.get("/api/v1/topics", headers=headers)).json())

    # PATCH ubah konten lain juga bekerja
    r = await client.patch(f"/api/v1/admin/topics/{slug}", headers=headers, json={"name": "Lifecycle Baru"})
    assert r.json()["name"] == "Lifecycle Baru"

    # unpublish -> published_at reset null & hilang dari publik
    r = await client.patch(f"/api/v1/admin/topics/{slug}", headers=headers, json={"is_published": False})
    assert r.json()["published_at"] is None
    assert not any(
        t["slug"] == slug for t in (await client.get("/api/v1/topics", headers=headers)).json()
    )

    # delete -> hilang total
    assert (await client.delete(f"/api/v1/admin/topics/{slug}", headers=headers)).status_code == 204
    assert (
        await client.get(f"/api/v1/topics/{slug}", headers=headers)
    ).status_code == 404


async def test_patch_empty_body_422(client, as_admin):
    headers = await as_admin()
    await client.post(
        "/api/v1/admin/topics", headers=headers, json={"slug": "kosong-uji", "name": "K", "summary": "s"}
    )
    r = await client.patch("/api/v1/admin/topics/kosong-uji", headers=headers, json={})
    assert r.status_code == 422


async def test_search_and_category_filter(client, as_admin):
    headers = await as_admin()

    async def _mk(slug, name, category, alt):
        r = await client.post(
            "/api/v1/admin/topics",
            headers=headers,
            json={
                "slug": slug, "name": name, "category": category,
                "summary": f"Ringkasan {name}.", "alt_names": alt, "is_published": True,
            },
        )
        assert r.status_code == 201

    await _mk("depresi-uji", "Depresi Uji", "mood", ["murung berkepanjangan"])
    await _mk("gad-uji", "GAD Uji", "anxiety", ["cemas berlebih"])

    r = await client.get("/api/v1/topics", params={"q": "murung"}, headers=headers)
    assert [t["slug"] for t in r.json()] == ["depresi-uji"]  # match via alt_names

    r = await client.get("/api/v1/topics", params={"category": "anxiety"}, headers=headers)
    slugs = {t["slug"] for t in r.json()}
    assert "gad-uji" in slugs and "depresi-uji" not in slugs

    r = await client.get("/api/v1/topics", params={"q": "zzz-tidak-ada"}, headers=headers)
    assert r.json() == []

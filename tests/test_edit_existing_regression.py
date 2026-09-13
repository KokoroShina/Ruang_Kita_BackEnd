"""Reproduksi bug laporan user: edit konten/topik yang SUDAH ADA → PATCH
image_url/summary → data baru HARUS terbaca lewat endpoint publik.

Menguja jalur yang sama dengan form admin FE:
1. POST create (published) tanpa gambar
2. PATCH dengan image_url (thumbnail YouTube) + source_url youtube
3. PATCH title/summary (edit isian lain)
4. GET list/detail publik — nilai harus yang terbaru
"""

YT = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
THUMB = "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg"


async def test_edit_existing_content_updates_visible(client, make_user, as_admin):
    admin_h = await as_admin("admin-edit1@test.id")

    # 1. Buat konten published tanpa gambar
    r = await client.post(
        "/api/v1/admin/content",
        headers=admin_h,
        json={
            "slug": "latihan-edit",
            "title": "Judul Awal",
            "content_type": "video",
            "summary": "Ringkasan awal.",
            "is_published": True,
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["image_url"] is None

    # 2. Edit: tambah link YouTube + thumbnail (persis alur admin FE)
    r = await client.patch(
        "/api/v1/admin/content/latihan-edit",
        headers=admin_h,
        json={"source_url": YT, "image_url": THUMB},
    )
    assert r.status_code == 200, r.text
    assert r.json()["image_url"] == THUMB

    # 3. Edit lagi: ubah judul + summary
    r = await client.patch(
        "/api/v1/admin/content/latihan-edit",
        headers=admin_h,
        json={"title": "Judul Baru", "summary": "Ringkasan baru."},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["title"] == "Judul Baru"
    # Edit field lain TIDAK boleh menghapus image_url
    assert body["image_url"] == THUMB, "image_url hilang setelah edit field lain!"

    # 4. Endpoint publik membaca data terbaru
    h = await make_user("warga-edit1@test.id")
    items = (await client.get("/api/v1/content", headers=h)).json()
    match = next(i for i in items if i["slug"] == "latihan-edit")
    assert match["title"] == "Judul Baru"
    assert match["summary"] == "Ringkasan baru."
    assert match["image_url"] == THUMB
    assert match["source_url"] == YT


async def test_edit_existing_topic_updates_visible(client, make_user, as_admin):
    admin_h = await as_admin("admin-edit2@test.id")

    r = await client.post(
        "/api/v1/admin/topics",
        headers=admin_h,
        json={
            "slug": "topik-edit",
            "name": "Nama Awal",
            "category": "mood",
            "summary": "Ringkasan awal.",
            "is_published": True,
        },
    )
    assert r.status_code == 201, r.text

    # Edit: tambah cover + ganti summary
    r = await client.patch(
        "/api/v1/admin/topics/topik-edit",
        headers=admin_h,
        json={"image_url": THUMB, "summary": "Ringkasan baru topik."},
    )
    assert r.status_code == 200, r.text
    assert r.json()["image_url"] == THUMB

    # Publik: list & detail membaca terbaru
    h = await make_user("warga-edit2@test.id")
    topics = (await client.get("/api/v1/topics", headers=h)).json()
    match = next(t for t in topics if t["slug"] == "topik-edit")
    assert match["summary"] == "Ringkasan baru topik."
    assert match["image_url"] == THUMB

    detail = (await client.get("/api/v1/topics/topik-edit", headers=h)).json()
    assert detail["image_url"] == THUMB


async def test_full_payload_edit_keeps_all_fields(client, make_user, as_admin):
    """Alur FE sesungguhnya: form mengirim SEMUA field (assign semua nilai),
    termasuk image_url. PATCH harus idempotent terhadap field yang sama."""
    admin_h = await as_admin("admin-edit3@test.id")

    r = await client.post(
        "/api/v1/admin/content",
        headers=admin_h,
        json={
            "slug": "konten-full",
            "title": "Awal",
            "content_type": "video",
            "summary": "Awal.",
            "topics": ["mood"],
            "is_published": True,
        },
    )
    assert r.status_code == 201

    # Payload lengkap ala FE (content-form assign semua field terisi)
    r = await client.patch(
        "/api/v1/admin/content/konten-full",
        headers=admin_h,
        json={
            "title": "Sesudah",
            "content_type": "video",
            "summary": "Sesudah.",
            "topics": ["mood", "anxiety"],
            "source_url": YT,
            "image_url": THUMB,
            "language": "id",
            "is_published": True,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["title"] == "Sesudah"
    assert body["topics"] == ["mood", "anxiety"]
    assert body["image_url"] == THUMB

    h = await make_user("warga-edit3@test.id")
    items = (await client.get("/api/v1/content", headers=h)).json()
    match = next(i for i in items if i["slug"] == "konten-full")
    assert match["title"] == "Sesudah"
    assert match["image_url"] == THUMB


async def test_empty_string_clears_image_url(client, make_user, as_admin):
    """Regression: image_url="" (string kosong) HARUS menghapus gambar —
    bukan diabaikan. Bug lama: zod FE menormalkan "" -> undefined sehingga
    PATCH tidak membawa perubahan sama sekali."""
    admin_h = await as_admin("admin-edit4@test.id")

    r = await client.post(
        "/api/v1/admin/content",
        headers=admin_h,
        json={
            "slug": "konten-clear",
            "title": "Konten Clear",
            "summary": "Awal.",
            "image_url": THUMB,
            "is_published": True,
        },
    )
    assert r.status_code == 201
    assert r.json()["image_url"] == THUMB

    # PATCH string kosong -> hapus
    r = await client.patch(
        "/api/v1/admin/content/konten-clear",
        headers=admin_h,
        json={"image_url": ""},
    )
    assert r.status_code == 200, r.text
    assert r.json()["image_url"] in (None, ""), "string kosong harus menghapus gambar"

    # Field lain tak tersentuh
    assert r.json()["title"] == "Konten Clear"
    assert r.json()["is_published"] is True


async def test_topic_myths_and_resources_roundtrip(client, make_user, as_admin):
    """Regression: form topik FE kini mengirim myths_facts & support_resources
    (dulu tidak pernah di-assign). Pastikan PATCH menyimpan keduanya dan
    terbaca publik."""
    admin_h = await as_admin("admin-edit5@test.id")

    r = await client.post(
        "/api/v1/admin/topics",
        headers=admin_h,
        json={
            "slug": "topik-mitos",
            "name": "Topik Mitos",
            "category": "mood",
            "summary": "Awal.",
            "is_published": True,
        },
    )
    assert r.status_code == 201

    r = await client.patch(
        "/api/v1/admin/topics/topik-mitos",
        headers=admin_h,
        json={
            "myths_facts": [
                {"myth": "Mitos satu", "fact": "Fakta satu"},
                {"myth": "Mitos dua", "fact": "Fakta dua"},
            ],
            "support_resources": [
                {"name": "SEJIWA", "contact": "119 ext. 8", "description": "24 jam"}
            ],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["myths_facts"]) == 2
    assert body["myths_facts"][0]["fact"] == "Fakta satu"
    assert body["support_resources"][0]["name"] == "SEJIWA"

    h = await make_user("warga-edit5@test.id")
    detail = (await client.get("/api/v1/topics/topik-mitos", headers=h)).json()
    assert len(detail["myths_facts"]) == 2
    assert detail["support_resources"][0]["contact"] == "119 ext. 8"

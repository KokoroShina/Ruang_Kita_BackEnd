"""Test fitur image_url (thumbnail/cover) untuk konten & topik + upload admin.

Hybrid: image_url bisa URL eksternal (thumbnail YouTube) atau path upload
lokal (/media/uploads/<file>) hasil POST /admin/uploads/image.
"""

import io
from pathlib import Path

from app.core.config import settings


def _tiny_png() -> bytes:
    """PNG 1x1 valid minimal (magic + IHDR + IDCT stub) — cukup untuk upload
    karena validasi hanya tipe MIME + ukuran, bukan dekode isi gambar."""
    return (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
        b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )


async def test_content_image_url_lifecycle(client, make_user, as_admin):
    admin_h = await as_admin("admin-img@test.id")

    # Create dengan thumbnail YouTube
    thumb = "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg"
    r = await client.post(
        "/api/v1/admin/content",
        headers=admin_h,
        json={
            "slug": "video-img",
            "title": "Video Thumbnail",
            "content_type": "video",
            "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "image_url": thumb,
            "is_published": True,
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["image_url"] == thumb

    # Terbaca di list public
    h = await make_user("warga-img@test.id")
    items = (await client.get("/api/v1/content", headers=h)).json()
    match = next(i for i in items if i["slug"] == "video-img")
    assert match["image_url"] == thumb

    # PATCH ganti gambar
    hq = "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg"
    r = await client.patch(
        "/api/v1/admin/content/video-img", headers=admin_h, json={"image_url": hq}
    )
    assert r.status_code == 200 and r.json()["image_url"] == hq


async def test_topic_image_url(client, make_user, as_admin):
    admin_h = await as_admin("admin-topikimg@test.id")

    r = await client.post(
        "/api/v1/admin/topics",
        headers=admin_h,
        json={
            "slug": "topik-img",
            "name": "Topik Bercover",
            "category": "mood",
            "summary": "Ringkasan.",
            "image_url": "https://contoh.example/cover.jpg",
            "is_published": True,
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["image_url"] == "https://contoh.example/cover.jpg"

    # Detail public membawa image_url
    h = await make_user("warga-topikimg@test.id")
    detail = (await client.get("/api/v1/topics/topik-img", headers=h)).json()
    assert detail["image_url"] == "https://contoh.example/cover.jpg"


async def test_admin_upload_image_success_and_guards(client, as_admin, make_user):
    admin_h = await as_admin("admin-upload@test.id")

    # Upload sukses → path /media/uploads/<hash>.png tersimpan di disk
    r = await client.post(
        "/api/v1/admin/uploads/image",
        headers=admin_h,
        files={"file": ("cover.png", io.BytesIO(_tiny_png()), "image/png")},
    )
    assert r.status_code == 201, r.text
    public_path = r.json()["image_url"]
    assert public_path.startswith("/media/uploads/")
    assert (Path(settings.MEDIA_DIR) / "uploads" / Path(public_path).name).exists()

    # Tipe tidak diizinkan → 422
    r = await client.post(
        "/api/v1/admin/uploads/image",
        headers=admin_h,
        files={"file": ("skrip.txt", io.BytesIO(b"echo hi"), "text/plain")},
    )
    assert r.status_code == 422

    # Non-admin → 403
    hB = await make_user("warga-upload@test.id")
    r = await client.post(
        "/api/v1/admin/uploads/image",
        headers=hB,
        files={"file": ("cover.png", io.BytesIO(_tiny_png()), "image/png")},
    )
    assert r.status_code == 403

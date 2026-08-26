"""Import/upsert konten psikoedukasi (content_library) dari JSON ke database.

Usage:
    .\\.venv\\Scripts\\python.exe scripts\\import_content.py                 # dry-run
    .\\.venv\\Scripts\\python.exe scripts\\import_content.py --apply         # simpan sesuai is_published di JSON
    .\\.venv\\Scripts\\python.exe scripts\\import_content.py --apply --publish  # paksa semua published

Idempotent by slug — jalankan ulang untuk update.
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.content_library import ContentLibrary  # noqa: E402

SEED_FILE = Path(__file__).parent / "content_seed.json"


async def upsert_item(row: dict, force_publish: bool) -> tuple[str, str]:
    async with AsyncSessionLocal() as db:
        slug = row["slug"].strip().lower()
        existing = (
            await db.execute(select(ContentLibrary).where(ContentLibrary.slug == slug))
        ).scalar_one_or_none()

        fields = {
            "title": row["title"],
            "summary": row.get("summary"),
            "content_body": row.get("content_body"),
            "content_type": row.get("content_type", "article"),
            "topics": [t.lower() for t in row.get("topics", [])],
            "source_url": row.get("source_url"),
            "duration_minutes": row.get("duration_minutes"),
            "language": row.get("language", "id"),
        }

        def _pub(row_: dict) -> bool:
            return force_publish or bool(row_.get("is_published"))

        if existing is None:
            is_published = _pub(row)
            item = ContentLibrary(
                slug=slug,
                **fields,
                is_published=is_published,
                published_at=(
                    datetime.now(timezone.utc).replace(tzinfo=None) if is_published else None
                ),
            )
            db.add(item)
            await db.commit()
            return slug, "created"

        for key, value in fields.items():
            setattr(existing, key, value)
        if force_publish:
            if not existing.is_published and existing.published_at is None:
                existing.published_at = datetime.now(timezone.utc).replace(tzinfo=None)
            existing.is_published = True
        await db.commit()
        return slug, "updated"


async def main() -> None:
    apply = "--apply" in sys.argv
    publish = "--publish" in sys.argv

    rows = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    print(f"{len(rows)} item konten ditemukan di {SEED_FILE.name}")
    if not apply:
        print("DRY-RUN — tambahkan --apply untuk benar-benar menyimpan.\n")

    for row in rows:
        if not apply:
            status_pub = "publish" if (publish or row.get("is_published")) else "draft"
            print(f"  [preview] {row['slug']:35s} ({row.get('content_type', 'article')}, {status_pub})")
            continue
        try:
            slug, action = await upsert_item(row, publish)
            print(f"  [{action}] {slug}")
        except Exception as exc:  # noqa: BLE001
            print(f"  [GAGAL] {row.get('slug', '?')}: {exc}")

    print("\nSelesai.")


if __name__ == "__main__":
    asyncio.run(main())

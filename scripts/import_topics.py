"""Import/upsert topik ensiklopedia dari JSON ke database.

Usage:
    .\\.venv\\Scripts\\python.exe scripts\\import_topics.py                    # dry-run (preview)
    .\\.venv\\Scripts\\python.exe scripts\\import_topics.py --apply            # import, tetap draft
    .\\.venv\\Scripts\\python.exe scripts\\import_topics.py --apply --publish # import + langsung published

Format file: lihat topics_seed.json di folder yang sama.
Idempotent by slug — jalankan ulang kapan pun untuk update konten.
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.mental_health_topic import MentalHealthTopic  # noqa: E402

SEED_FILE = Path(__file__).parent / "topics_seed.json"


async def upsert_topic(row: dict, publish: bool) -> tuple[str, str]:
    """Return (slug, action) — action: created | updated."""
    async with AsyncSessionLocal() as db:
        slug = row["slug"].strip().lower()
        existing = (
            await db.execute(select(MentalHealthTopic).where(MentalHealthTopic.slug == slug))
        ).scalar_one_or_none()

        fields = {
            "name": row["name"],
            "alt_names": row.get("alt_names", []),
            "category": row.get("category", "other"),
            "summary": row["summary"],
            "signs_symptoms": row.get("signs_symptoms", []),
            "causes_risk_factors": row.get("causes_risk_factors"),
            "coping_treatment": row.get("coping_treatment"),
            "myths_facts": row.get("myths_facts", []),
            "when_to_seek_help": row.get("when_to_seek_help"),
            "support_resources": row.get("support_resources", []),
            "related_topic_slugs": row.get("related_topic_slugs", []),
            "sources": row.get("sources"),
            "language": row.get("language", "id"),
        }

        if existing is None:
            is_published = publish or bool(row.get("is_published"))
            topic = MentalHealthTopic(
                slug=slug,
                **fields,
                is_published=is_published,
                published_at=(
                    datetime.now(timezone.utc).replace(tzinfo=None) if is_published else None
                ),
            )
            db.add(topic)
            await db.commit()
            return slug, "created"

        for key, value in fields.items():
            setattr(existing, key, value)
        if publish:
            if not existing.is_published and existing.published_at is None:
                existing.published_at = datetime.now(timezone.utc).replace(tzinfo=None)
            existing.is_published = True
        await db.commit()
        return slug, "updated"


async def main() -> None:
    apply = "--apply" in sys.argv
    publish = "--publish" in sys.argv

    rows = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    print(f"{len(rows)} topik ditemukan di {SEED_FILE.name}")
    if not apply:
        print("DRY-RUN — tambahkan --apply untuk benar-benar menyimpan.\n")

    for row in rows:
        if not apply:
            status_pub = "publish" if (publish or row.get("is_published")) else "draft"
            print(f"  [preview] {row['slug']:40s} ({row.get('category', 'other')}, {status_pub})")
            continue
        try:
            slug, action = await upsert_topic(row, publish=publish)
            print(f"  [{action}] {slug}")
        except Exception as exc:  # noqa: BLE001 — lanjut baris berikutnya
            print(f"  [GAGAL] {row.get('slug', '?')}: {exc}")

    print("\nSelesai.")


if __name__ == "__main__":
    asyncio.run(main())

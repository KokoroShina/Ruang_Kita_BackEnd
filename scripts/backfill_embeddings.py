"""Backfill embedding vektor utk semua topik & konten PUBLISHED yang belum ter-embed.

Jalankan setelah mengisi GEMINI_API_KEY (gratis: https://aistudio.google.com/apikey):
    .\\.venv\\Scripts\\python.exe scripts\\backfill_embeddings.py            # preview
    .\\.venv\\Scripts\\python.exe scripts\\backfill_embeddings.py --apply     # embed
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import AsyncSessionLocal, engine  # noqa: E402
from app.models.content_library import ContentLibrary  # noqa: E402
from app.models.mental_health_topic import MentalHealthTopic  # noqa: E402
from app.services.ai import embeddings as emb  # noqa: E402


async def main() -> None:
    if "--apply" not in sys.argv:
        print("DRY-RUN — tambahkan --apply untuk benar-benar meng-embed.\n")

    print(f"Semantik aktif: {emb.is_enabled()} "
          f"(GEMINI_API_KEY={'ada' if settings.GEMINI_API_KEY else 'KOSONG'}, "
          f"model={settings.EMBEDDING_MODEL})\n")

    total_ok = total_skip = total_fail = 0

    async with AsyncSessionLocal() as db:
        topics = (
            await db.execute(
                select(MentalHealthTopic).where(
                    MentalHealthTopic.is_published.is_(True),
                    MentalHealthTopic.embedding.is_(None),
                )
            )
        ).scalars().all()
        for t in topics:
            print(f"  [topik]   {t.slug:40s}", end=" ")
            if not emb.is_enabled():
                print("SKIP (tanpa key)")
                total_skip += 1
                continue
            ok = await emb.embed_and_store_topic(db, t)
            print("OK" if ok else "GAGAL")
            total_ok += int(ok) or 0
            total_fail += 0 if ok else 1

        contents = (
            await db.execute(
                select(ContentLibrary).where(
                    ContentLibrary.is_published.is_(True),
                    ContentLibrary.embedding.is_(None),
                )
            )
        ).scalars().all()
        for c in contents:
            print(f"  [konten]  {c.slug:40s}", end=" ")
            if not emb.is_enabled():
                print("SKIP (tanpa key)")
                total_skip += 1
                continue
            ok = await emb.embed_and_store_content(db, c)
            print("OK" if ok else "GAGAL")
            total_ok += int(ok) or 0
            total_fail += 0 if ok else 1

    await engine.dispose()
    print(f"\nSelesai — embedded: {total_ok} · skip: {total_skip} · gagal: {total_fail}")


if __name__ == "__main__":
    asyncio.run(main())

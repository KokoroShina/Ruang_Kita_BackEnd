"""Backfill image_url (+ video_url topik) dari thumbnail video YouTube edukasi.

Usage:
    .\\.venv\\Scripts\\python.exe scripts\\backfill_images.py          # dry-run (preview)
    .\\.venv\\Scripts\\python.exe scripts\\backfill_images.py --apply  # tulis ke DB

Sumber gambar: thumbnail resmi YouTube (i.ytimg.com) dari video edukasi
kesehatan mental berbahasa Indonesia — pola sama dengan yang sudah dipakai
topik academic-stress & konten grounding-54321.

Idempotent: hanya mengisi slot KOSONG. Slot yang sudah diisi admin
(gambar upload lokal / URL lain) tidak pernah ditimpa. Jalankan ulang
kapan pun setelah menambah topik/konten baru.

video_url hanya untuk mental_health_topics (konten tidak punya field video).
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.content_library import ContentLibrary  # noqa: E402
from app.models.mental_health_topic import MentalHealthTopic  # noqa: E402

# Hasil riset (Sept 2026): video edukasi berbahasa Indonesia per topik/konten.
# slug -> (youtube_video_id, judul_singkat)
# Topik gangguan-kecemasan-umum-gad sengaja tidak diisi (draft duplikat dari
# generalized-anxiety-disorder yang published).
VIDEO_MAP: dict[str, tuple[str, str]] = {
    # ── Topik ensiklopedia ──────────────────────────────────────────────
    "burnout": ("aakMc6bOjdw", "Apa itu Burnout? — Neuron and Hipotesa"),
    "ptsd": ("JbpArOwlmeE", "Kenalan Dengan Complex PTSD — Jiemi Ardian"),
    "generalized-anxiety-disorder": ("KpQzF4rCo-Y", "GAD: Beda dengan Overthinking — MHI"),
    "major-depressive-disorder": ("wr2IqS8bsS4", "Apa itu Depresi? — Neuron and Hipotesa"),
    "fear-of-missing-out-fomo": ("f3csuWXH7OA", "On Marissa's Mind: FOMO — Greatmind"),
    "impostor-phenomenon": ("24d-rKJC72o", "Impostor Syndrome — 1 Hari Sukses"),
    "loneliness": ("rKrIJnfbeCo", "Loneliness alias Kesepian — Bahas Psikologi"),
    "perfectionism": ("AazRCNN-YAo", "Perfeksionis — Jiemi Ardian"),
    "rumination": ("vtjoiui939I", "Psikologi Overthinking — Pikiran Sederhana"),
    "anorexia-nervosa": ("RT4w4XKONgs", "Gangguan Makan — dr.Emasuperr"),
    "academic-stress": ("hMg_wA-OFQ4", "Stres Akademik Mahasiswa"),
    # ── Konten library ──────────────────────────────────────────────────
    "jurnal-gratitude-harian": ("-2UcneA2SLg", "Jurnal Syukur Harian — Kunci Hidup"),
    "mengenali-pemicu-overthinking": ("VqY1fBptc2g", "Kenali Pikiranmu — Satu Persen"),
    "napas-478": ("lEzaFx8k7Ew", "Latihan Pernapasan 4-7-8 — Hands-On Meditation"),
}


async def resolve_thumb(vid: str) -> str | None:
    """maxresdefault → fallback hqdefault; None bila keduanya tidak ada."""
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for quality in ("maxresdefault", "hqdefault"):
            url = f"https://i.ytimg.com/vi/{vid}/{quality}.jpg"
            try:
                r = await client.head(url)
                if r.status_code == 200:
                    return url
            except httpx.HTTPError:
                continue
    return None


async def run(apply: bool) -> None:
    stats = {"topic_img": 0, "topic_vid": 0, "content_img": 0, "skip_filled": 0, "no_thumb": 0}

    async with AsyncSessionLocal() as db:
        # ── Topik ────────────────────────────────────────────────────────
        topics = (
            (await db.execute(select(MentalHealthTopic))).scalars().all()
        )
        by_slug = {t.slug: t for t in topics}

        for slug, (vid, title) in VIDEO_MAP.items():
            topic = by_slug.get(slug)
            if topic is None:
                print(f"  [SKIP] {slug}: topik tidak ada di DB")
                continue
            if topic.image_url and topic.video_url:
                stats["skip_filled"] += 1
                continue

            thumb = await resolve_thumb(vid)
            if not thumb:
                print(f"  [WARN] {slug}: thumbnail tidak tersedia ({title})")
                stats["no_thumb"] += 1
                continue

            changed = []
            if not topic.image_url:
                topic.image_url = thumb
                changed.append("image_url")
                stats["topic_img"] += 1
            if not topic.video_url:
                topic.video_url = f"https://www.youtube.com/watch?v={vid}"
                changed.append("video_url")
                stats["topic_vid"] += 1
            print(f"  [TOPIC] {slug}: set {', '.join(changed)} <- {title}")

        # ── Konten ───────────────────────────────────────────────────────
        contents = (await db.execute(select(ContentLibrary))).scalars().all()
        by_slug_c = {c.slug: c for c in contents}

        for slug, (vid, title) in VIDEO_MAP.items():
            item = by_slug_c.get(slug)
            if item is None:
                continue
            if item.image_url:
                continue
            thumb = await resolve_thumb(vid)
            if not thumb:
                print(f"  [WARN] {slug}: thumbnail tidak tersedia ({title})")
                stats["no_thumb"] += 1
                continue
            item.image_url = thumb
            stats["content_img"] += 1
            print(f"  [CONTENT] {slug}: set image_url <- {title}")

        if apply:
            await db.commit()
            print(f"\nOK {stats}")
        else:
            await db.rollback()
            print(f"\n[DRY-RUN] {stats} — jalankan dengan --apply untuk menulis.")


if __name__ == "__main__":
    asyncio.run(run(apply="--apply" in sys.argv))

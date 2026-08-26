"""Impor massal konten ensiklopedia topik kesehatan mental (berbasis API).

Berbeda dari import_topics.py (seed manual -> tulis langsung ke DB), skrip ini
mengirim konten lewat API yang sama dengan production: login JWT sebagai akun
admin, lalu POST /api/v1/admin/topics per topik. Konten dibaca dari berkas JSON
di data/topics/*.json (payload persis seperti body TopicCreate) yang dihasilkan
lewat riset + penulisan per batch.

Validasi ganda sebelum POST:
  1. Pydantic TopicCreate (app/schemas/topic.py) + aturan kebijakan impor
     (language="id", is_published=false).
  2. Server: slug unik -> HTTP 409 tercatat sebagai SKIPPED_DUPLICATE.

Resumable: hasil tiap topik append ke data/import/results.jsonl. Saat dijalankan
lagi, topik SUCCESS / SKIPPED_DUPLICATE dilewati — aman berhenti-lanjut tanpa
duplikasi (analogi job queue Laravel yang idempotent).

Default TANPA uvicorn: request jalan in-process lewat httpx.ASGITransport ke
aplikasi FastAPI yang sama (endpoint/service/db identik). Pakai --base-url
untuk menembak server yang sedang hidup.

Status hasil: SUCCESS | SKIPPED_DUPLICATE | VALIDATION_ERROR | API_ERROR

Usage:
    .\\.venv\\Scripts\\python.exe scripts\\import_topics_bulk.py --list
    .\\.venv\\Scripts\\python.exe scripts\\import_topics_bulk.py --dry-run
    .\\.venv\\Scripts\\python.exe scripts\\import_topics_bulk.py --limit 10
    .\\.venv\\Scripts\\python.exe scripts\\import_topics_bulk.py --slug burnout,fomo
    .\\.venv\\Scripts\\python.exe scripts\\import_topics_bulk.py --retry-failed
    .\\.venv\\Scripts\\python.exe scripts\\import_topics_bulk.py --force
    .\\.venv\\Scripts\\python.exe scripts\\import_topics_bulk.py --base-url http://127.0.0.1:8000
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.schemas.topic import TopicCreate  # noqa: E402

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = ROOT / "data" / "topics"
RESULTS_PATH = ROOT / "data" / "import" / "results.jsonl"

# Status final yang tidak perlu diproses ulang saat resume.
DONE_STATUSES = {"SUCCESS", "SKIPPED_DUPLICATE"}
RETRYABLE_HTTP_STATUS = {500, 502, 503, 504}


def load_results() -> dict[str, str]:
    """Baca results.jsonl -> map slug -> status terakhir per slug."""
    latest: dict[str, str] = {}
    if not RESULTS_PATH.exists():
        return latest
    for line in RESULTS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        slug = row.get("slug")
        status = row.get("status")
        if slug and status:
            latest[slug] = status
    return latest


def record_result(row: dict) -> None:
    """Append satu baris hasil ke results.jsonl (append-only, aman untuk resume)."""
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {"timestamp": datetime.now(timezone.utc).isoformat(), **row}
    with RESULTS_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_content_files(slug_filter: set[str] | None) -> list[tuple[Path, dict]]:
    """Muat semua *.json konten urut abjad. Return [(path, payload)]."""
    if not CONTENT_DIR.exists():
        sys.exit(f"Direktori konten tidak ada: {CONTENT_DIR} (buat dulu berkas kontennya)")

    items: list[tuple[Path, dict]] = []
    seen_slugs: dict[str, Path] = {}
    for path in sorted(CONTENT_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"  [VALIDATION_ERROR] {path.name}: JSON rusak ({exc})")
            continue

        slug = payload.get("slug")
        if slug_filter and slug not in slug_filter:
            continue

        if slug in seen_slugs:
            # Dua berkas beda nama dengan slug sama -> berkas kedua catat duplikat.
            items.append(
                (
                    path,
                    {
                        "slug": str(slug),
                        "name": payload.get("name", path.stem),
                        "_prefail": (
                            "SKIPPED_DUPLICATE",
                            f"slug sama dengan {seen_slugs[slug].name}",
                        ),
                    },
                )
            )
            continue
        seen_slugs[slug] = path
        items.append((path, payload))
    return items


def validate_payload(payload: dict) -> tuple[TopicCreate | None, str | None]:
    """Validasi payload terhadap TopicCreate + aturan kebijakan impor.

    Return (payload_valid, pesan_error); error None berarti lolos.
    """
    try:
        topic = TopicCreate.model_validate(payload)
    except Exception as exc:  # pydantic ValidationError
        return None, str(exc)

    # Kebijakan impor: selalu Bahasa Indonesia, selalu draft (tidak auto-publish).
    if topic.language != "id":
        return None, f'language harus "id" (dapat: {topic.language!r})'
    if topic.is_published:
        return None, "is_published harus false — konten hasil riset AI tidak auto-publish"
    return topic, None


async def build_client(base_url: str | None) -> tuple[httpx.AsyncClient, bool]:
    """Buat httpx client. Return (client, in_process)."""
    if base_url:
        return httpx.AsyncClient(base_url=base_url, timeout=30.0), False
    # In-process: tanpa server hidup — kode endpoint/service/db identik.
    from main import app as fastapi_app

    transport = httpx.ASGITransport(app=fastapi_app)
    return (
        httpx.AsyncClient(
            transport=transport,
            base_url="http://importer.local",
            timeout=30.0,
        ),
        True,
    )


async def login(client: httpx.AsyncClient) -> str:
    """Login akun importer -> access token JWT."""
    email = settings.IMPORT_ADMIN_EMAIL
    password = settings.IMPORT_ADMIN_PASSWORD
    if not email or not password:
        sys.exit(
            "IMPORT_ADMIN_EMAIL / IMPORT_ADMIN_PASSWORD belum diisi di .env "
            "(emailnya harus terdaftar di ADMIN_EMAILS)."
        )

    resp = await client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        json={"email": email, "password": password},
    )
    if resp.status_code != 200:
        sys.exit(f"Login gagal ({resp.status_code}): {resp.text}")
    data = resp.json()
    if not data.get("is_admin"):
        sys.exit(f"{email} tidak terdaftar di ADMIN_EMAILS — endpoint admin akan 403.")
    return data["access_token"]


async def post_topic(
    client: httpx.AsyncClient, token: str, topic: TopicCreate
) -> tuple[str, int | None, str | None]:
    """POST satu topik. Return (status, http_status, pesan_error)."""
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{settings.API_V1_PREFIX}/admin/topics"
    body = topic.model_dump(mode="json")

    # Retry 1x hanya untuk galat sementara (jaringan / 5xx) — bukan validasi.
    for attempt in (1, 2):
        try:
            resp = await client.post(url, json=body, headers=headers)
        except httpx.TransportError as exc:
            if attempt == 1:
                logger.warning("TransportError (%s), retry 1x...", exc)
                await asyncio.sleep(2)
                continue
            return "API_ERROR", None, f"transport: {exc}"

        if resp.status_code == 201:
            return "SUCCESS", 201, None
        if resp.status_code == 409:
            return "SKIPPED_DUPLICATE", 409, str(resp.json().get("detail"))
        if resp.status_code in RETRYABLE_HTTP_STATUS and attempt == 1:
            await asyncio.sleep(2)
            continue
        return "API_ERROR", resp.status_code, resp.text[:300]
    return "API_ERROR", None, "unreachable"


async def run(args: argparse.Namespace) -> None:
    slug_filter = {s.strip() for s in args.slug.split(",") if s.strip()} if args.slug else None
    items = load_content_files(slug_filter)
    latest = load_results()

    if args.list:
        print(f"{'STATUS':<19} {'SLUG':<42} SUMBER")
        for path, payload in items:
            slug = str(payload.get("slug", "?"))
            name = str(payload.get("name", "-"))[:34]
            status = latest.get(slug, "BELUM")
            print(f"{status:<19} {slug:<42} {path.name}  ({name})")
        done = sum(
            1 for _, p in items if latest.get(str(p.get("slug"))) in DONE_STATUSES
        )
        print(f"\nTotal: {len(items)} | selesai: {done} | sisa: {len(items) - done}")
        return

    if not items:
        sys.exit(f"Tidak ada berkas konten yang cocok di {CONTENT_DIR}")

    # Tentukan daftar kerja sesuai kebijakan resume.
    work: list[tuple[Path, dict]] = []
    skipped_resume = 0
    for path, payload in items:
        slug = str(payload.get("slug"))
        prev = latest.get(slug)
        if prev in DONE_STATUSES and not args.force:
            skipped_resume += 1
            continue
        if (
            prev in {"VALIDATION_ERROR", "API_ERROR"}
            and not args.retry_failed
            and not args.force
        ):
            skipped_resume += 1
            continue
        work.append((path, payload))

    if args.limit is not None:
        work = work[: max(args.limit, 0)]

    mode = " | DRY-RUN" if args.dry_run else ""
    print(f"Konten: {len(items)} | dilewati (resume): {skipped_resume} | diproses: {len(work)}{mode}")
    if not work:
        print("Tidak ada yang perlu diproses. (--force untuk proses ulang semuanya)")
        return

    counts = {
        "SUCCESS": 0,
        "SKIPPED_DUPLICATE": 0,
        "VALIDATION_ERROR": 0,
        "API_ERROR": 0,
    }
    client, in_process = await build_client(args.base_url)
    token: str | None = None
    start = time.perf_counter()
    try:
        if not args.dry_run:
            token = await login(client)

        for i, (path, payload) in enumerate(work, start=1):
            slug = str(payload.get("slug"))
            label = f"[{i}/{len(work)}] {slug}"

            # Prefail: duplikat slug dalam batch yang sama.
            if "_prefail" in payload:
                status, reason = payload["_prefail"]
                print(f"{label} -> {status} ({reason})")
                counts[status] += 1
                record_result({"topic": slug, "slug": slug, "status": status, "error": reason})
                continue

            topic, err = validate_payload(payload)
            if topic is None:
                first_line = err.splitlines()[0] if err else "?"
                print(f"{label} -> VALIDATION_ERROR: {first_line}")
                counts["VALIDATION_ERROR"] += 1
                record_result(
                    {"topic": slug, "slug": slug, "status": "VALIDATION_ERROR", "error": err}
                )
                continue

            if args.dry_run:
                print(f"{label} -> OK (dry-run, tidak dikirim)")
                continue

            status, http_status, error = await post_topic(client, token, topic)
            counts[status] += 1
            suffix = f" (HTTP {http_status}: {error})" if error else ""
            print(f"{label} -> {status}{suffix}")
            record_result(
                {
                    "topic": topic.name,
                    "slug": slug,
                    "status": status,
                    "http_status": http_status,
                    "error": error,
                }
            )
    finally:
        await client.aclose()
        if in_process:
            # Rapikan resource yang biasanya ditutup lifespan main.py.
            from app.db.session import engine
            from app.services.ai.embeddings import close_embed_client
            from app.services.ai.openrouter_client import close_openrouter_client

            await close_openrouter_client()
            await close_embed_client()
            await engine.dispose()

    elapsed = time.perf_counter() - start
    print(
        f"\nSelesai dalam {elapsed:.1f}s — "
        f"SUCCESS={counts['SUCCESS']} DUPLICATE={counts['SKIPPED_DUPLICATE']} "
        f"VALIDATION={counts['VALIDATION_ERROR']} API_ERROR={counts['API_ERROR']}"
    )
    print(f"Log hasil: {RESULTS_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Impor massal konten topik dari data/topics/*.json via POST /admin/topics"
    )
    parser.add_argument("--dry-run", action="store_true", help="Validasi saja, tanpa POST/login")
    parser.add_argument("--limit", type=int, default=None, help="Proses maksimal N topik")
    parser.add_argument("--slug", default=None, help="Proses slug tertentu saja (pisah koma)")
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Proses ulang topik yang sebelumnya VALIDATION_ERROR/API_ERROR",
    )
    parser.add_argument("--force", action="store_true", help="Abaikan riwayat resume, proses semua")
    parser.add_argument("--list", action="store_true", help="Tampilkan status semua berkas konten")
    parser.add_argument(
        "--base-url",
        default=None,
        help="URL server hidup (mis. http://127.0.0.1:8000). Default: in-process.",
    )
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()

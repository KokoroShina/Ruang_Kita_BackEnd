"""Buat user admin untuk endpoint konten (/admin/topics, /discover admin, dst).

Admin di project ini ditentukan lewat ADMIN_EMAILS di .env — bukan kolom role
di tabel users (lihat app/core/dependencies.py::get_current_admin). Script ini
mengerjakan kedua langkah sekaligus:
  1. Buat user di database (atau pakai user yang sudah ada).
  2. Masukkan emailnya ke daftar ADMIN_EMAILS di .env.

Usage:
    .\\.venv\\Scripts\\python.exe scripts\\create_admin.py --email admin@ruangkita.id
    .\\.venv\\Scripts\\python.exe scripts\\create_admin.py --email admin@ruangkita.id --password rahasia123 --name "Admin Ruang Kita"

Tanpa --password, diminta via prompt tersembunyi (tidak masuk riwayat shell).
Idempotent — user yang sudah ada dipakai apa adanya, email di .env tidak diduplikasi.
"""

import argparse
import asyncio
import getpass
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


async def ensure_user(email: str, password: str, name: str | None) -> str:
    """Buat user bila belum ada. Return 'dibuat' | 'sudah ada'."""
    async with AsyncSessionLocal() as db:
        existing = await db.scalar(select(User).where(User.email == email))
        if existing is not None:
            return "sudah ada"

        db.add(
            User(
                email=email,
                hashed_password=hash_password(password),
                full_name=name,
                consent_accepted_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()
        return "dibuat"


def upsert_env_admin_email(email: str) -> str:
    """Pastikan email masuk ADMIN_EMAILS di .env. Return 'ditambahkan' | 'sudah ada'."""
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    pattern = re.compile(r"^ADMIN_EMAILS\s*=\s*(.*)$")
    emails: list[str] = []
    found = False

    for i, line in enumerate(lines):
        match = pattern.match(line)
        if not match:
            continue
        found = True
        try:
            parsed = json.loads(match.group(1).strip())
            if isinstance(parsed, list):
                emails = [str(e).strip().lower() for e in parsed if str(e).strip()]
        except json.JSONDecodeError:
            print(f"  [peringatan] ADMIN_EMAILS di {ENV_PATH.name} tidak valid — dibuat ulang.")
        if email not in emails:
            emails.append(email)
        lines[i] = f"ADMIN_EMAILS={json.dumps(emails)}"
        break

    if not found:
        emails = [email]
        lines.append(f"ADMIN_EMAILS={json.dumps(emails)}")

    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return "ditambahkan" if email in emails else "gagal"


async def main() -> None:
    parser = argparse.ArgumentParser(description="Buat user admin + daftarkan emailnya ke .env")
    parser.add_argument("--email", required=True, help="Email akun admin")
    parser.add_argument("--password", help="Kosongkan agar diminta via prompt tersembunyi")
    parser.add_argument("--name", default=None, help="Nama lengkap (opsional)")
    args = parser.parse_args()

    email = args.email.strip().lower()
    if "@" not in email:
        sys.exit(f"Email tidak valid: {args.email!r}")

    password = args.password or getpass.getpass(f"Password untuk {email}: ")
    if not password:
        sys.exit("Password tidak boleh kosong")

    try:
        hash_password(password)  # validasi awal (mis. limit 72 byte bcrypt)
    except ValueError as exc:
        sys.exit(f"Password ditolak: {exc}")

    user_status = await ensure_user(email, password, args.name)
    print(f"[{user_status}] user {email}")

    env_status = upsert_env_admin_email(email)
    print(f"[{env_status}] ADMIN_EMAILS di {ENV_PATH}")

    if user_status == "dibuat" or env_status == "ditambahkan":
        print("\nRestart server agar .env terbaca ulang (settings di-cache saat startup).")


if __name__ == "__main__":
    asyncio.run(main())

"""Setup logging terpusat Ruang Kita.

Semua log (uvicorn access/error, middleware request, service, warning AI) mengalir
ke satu format yang sama: console + file harian `logs/app.log` — rotasi tengah
malam dengan backup `LOG_RETENTION_DAYS` hari. Level diatur via `LOG_LEVEL` (.env).

Panggil `setup_logging()` sekali saat startup (main.py). Analogi Laravel:
`storage/logs/laravel.log` -> `logs/app.log`, `Log::info()` -> `logger.info()`.
"""

import logging
import logging.handlers
import sys
from pathlib import Path

from app.core.config import settings

_FORMAT = "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"

# Logger pihak ketiga yang handler bawaannya dibuang supaya tidak dobel —
# propagate=True meneruskan rekamannya ke root (console + file).
_THIRD_PARTY_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")


def setup_logging() -> None:
    level = getattr(logging, settings.LOG_LEVEL.strip().upper(), logging.INFO)
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(_FORMAT, datefmt=_DATEFMT)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # delay=True -> file baru dibuat saat rekaman pertama (tidak ada file kosong)
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_dir / "app.log",
        when="midnight",
        backupCount=settings.LOG_RETENTION_DAYS,
        encoding="utf-8",
        delay=True,
    )
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(console_handler)
    root.addHandler(file_handler)

    for name in _THIRD_PARTY_LOGGERS:
        uv_logger = logging.getLogger(name)
        uv_logger.handlers.clear()
        uv_logger.propagate = True

    # SQL echo mode development punya handler sendiri dari SQLAlchemy (console polos).
    # Jangan diteruskan ke root agar tidak dobel dan file log tetap fokus ke event app.
    logging.getLogger("sqlalchemy.engine").propagate = False

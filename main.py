import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging_setup import setup_logging
from app.db.session import engine
from app.services.ai.embeddings import close_embed_client
from app.services.ai.openrouter_client import close_openrouter_client

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield
    await close_openrouter_client()
    await close_embed_client()
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="0.1.0",
        description=(
            "Backend PWA literasi kesejahteraan (wellbeing) untuk anak muda 15-23 tahun. "
            "Tiga pilar: Kenali (jurnal & mood), Pahami (chatbot refleksi AI), "
            "Temukan (rekomendasi konten personal)."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Log setiap request — analogi log lifecycle Laravel.
    # Health check cukup di DEBUG agar tidak berisik di level INFO.
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "%s %s -> 500 (%.0f ms)",
                request.method,
                request.url.path,
                (time.perf_counter() - start) * 1000,
            )
            raise
        elapsed_ms = (time.perf_counter() - start) * 1000
        log_fn = (
            logger.debug
            if request.url.path == f"{settings.API_V1_PREFIX}/health"
            else logger.info
        )
        log_fn(
            "%s %s -> %d (%.0f ms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @app.get("/", tags=["root"])
    async def root() -> dict[str, str]:
        return {
            "name": settings.PROJECT_NAME,
            "version": "0.1.0",
            "docs": "/docs",
            "health": f"{settings.API_V1_PREFIX}/health",
        }

    return app


app = create_app()

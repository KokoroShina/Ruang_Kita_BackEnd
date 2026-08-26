from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.ENVIRONMENT == "development",
    pool_pre_ping=True,
    connect_args={
        "charset": "utf8mb4",
        # DATETIME MySQL naive → paksa NOW()/CURRENT_TIMESTAMP dalam UTC agar konsisten
        "init_command": "SET time_zone = '+00:00'",
    },
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency FastAPI — commit/rollback dikelola oleh endpoint/service."""
    async with AsyncSessionLocal() as session:
        yield session

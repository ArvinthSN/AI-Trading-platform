from collections.abc import AsyncIterator
from functools import lru_cache

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    database_url = get_settings().database_url
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured.")
    engine = create_async_engine(database_url, pool_pre_ping=True)
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_database_session() -> AsyncIterator[AsyncSession]:
    try:
        factory = get_session_factory()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail="PostgreSQL is not configured.") from error
    async with factory() as session:
        yield session

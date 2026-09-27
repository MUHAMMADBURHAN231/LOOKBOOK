"""Database engines. The API uses async SQLAlchemy; Celery workers use a sync engine.
Both use psycopg 3 and connect as the least-privilege application role."""

from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def async_engine():
    return create_async_engine(
        get_settings().database_url, pool_size=10, max_overflow=20, pool_pre_ping=True
    )


@lru_cache
def _async_sessionmaker():
    return async_sessionmaker(async_engine(), expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, rolled back on error."""
    async with _async_sessionmaker()() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


@lru_cache
def sync_engine():
    return create_engine(get_settings().database_url, pool_size=5, max_overflow=5, pool_pre_ping=True)


@contextmanager
def sync_session() -> Iterator[Session]:
    session = sessionmaker(sync_engine(), expire_on_commit=False)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engines() -> None:
    """Drop cached engines (tests switch databases between runs)."""
    async_engine.cache_clear()
    _async_sessionmaker.cache_clear()
    sync_engine.cache_clear()

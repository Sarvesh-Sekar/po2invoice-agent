"""Async SQLAlchemy engine/session configuration.

The repository layer is the single database access abstraction for the
application — agents and services never issue raw SQL or use sessions
directly.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def configure_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    """Create (or recreate) the async engine and session factory."""
    global _engine, _session_factory
    if _engine is not None:
        import asyncio

        try:
            asyncio.get_running_loop().run_in_executor(None, _engine.sync_engine.dispose)
        except RuntimeError:
            _engine.sync_engine.dispose()

    kwargs: dict = {"echo": echo, "pool_pre_ping": True}
    if database_url.startswith("sqlite") and ":memory:" in database_url:
        # Every pooled connection would otherwise get its own empty in-memory DB.
        kwargs["poolclass"] = StaticPool
    _engine = create_async_engine(database_url, **kwargs)
    _session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    return _engine


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Database engine not configured; call configure_engine() first")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Database session factory not configured; call configure_engine() first")
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a scoped async session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def create_all() -> None:
    """Create all tables registered on the ORM metadata (startup only)."""
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all() -> None:
    """Drop all tables (tests only)."""
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def dispose() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None

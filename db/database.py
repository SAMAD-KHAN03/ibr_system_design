"""
db/database.py
==============
Async SQLAlchemy engine + session factory.

Driver   : asyncpg  (async PostgreSQL — required for FastAPI)
Target DB: AWS RDS PostgreSQL (or any PostgreSQL 14+)

Environment variable required:
    DATABASE_URL=postgresql+asyncpg://user:password@host:5432/dbname

On application startup, call init_db() once to create all tables.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://bra_user:bra_password@localhost:5432/bra_db",
)

# ---------------------------------------------------------------------------
# Engine
# Pool tuning for EC2 + RDS:
#   pool_size     — persistent connections kept alive (match RDS max_connections/num_workers)
#   max_overflow  — burst connections above pool_size
#   pool_recycle  — recycle connections every 30 min (avoids RDS idle timeout drops)
#   pool_pre_ping — test connection before use (handles RDS failover transparently)
# ---------------------------------------------------------------------------

engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800,
    pool_pre_ping=True,
    connect_args={
        "server_settings": {"application_name": "bra_api"},
    },
)

# ---------------------------------------------------------------------------
# Session factory
# expire_on_commit=False — keeps ORM objects accessible after commit in async context
# ---------------------------------------------------------------------------

AsyncSessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


# ---------------------------------------------------------------------------
# Base class for all ORM models
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Lifecycle helpers
# ---------------------------------------------------------------------------

async def init_db() -> None:
    """
    Creates all tables defined in ORM models.
    Safe to call on every startup — uses CREATE TABLE IF NOT EXISTS semantics.
    Call this once inside the FastAPI lifespan handler.
    """
    # Import models so Base.metadata is populated before create_all
    from db import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("Database tables initialised.")


async def close_db() -> None:
    """Dispose connection pool cleanly on shutdown."""
    await engine.dispose()
    log.info("Database connection pool closed.")


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for a DB session.
    Commits on clean exit, rolls back on exception.

    Usage (in non-FastAPI code, e.g. worker.py):
        async with get_session() as session:
            await repository.save_report(session, ...)
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency — injects an AsyncSession into route handlers.

    Usage:
        @app.get("/...")
        async def handler(db: AsyncSession = Depends(get_db_session)):
            ...
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

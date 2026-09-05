# app/db/session.py

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import DATABASE_URL

# Lazy cached singletons — created on first use, not at import time, so
# importing this module doesn't require DATABASE_URL to already be set
# (e.g. during local tooling that never touches the DB).
_engine = None
_sessionmaker = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
    return _engine


def get_sessionmaker():
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            get_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _sessionmaker


async def get_db():
    async with get_sessionmaker()() as session:
        yield session


async def init_models():
    from app.db import models  # noqa: F401 -- registers tables on Base.metadata
    from app.db.base import Base

    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

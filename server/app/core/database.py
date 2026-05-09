from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(self) -> None:
        self.engine: AsyncEngine | None = None
        self.session_factory: async_sessionmaker[AsyncSession] | None = None

    def configure(self, database_url: str) -> None:
        if self.engine is not None:
            return
        self.engine = create_async_engine(database_url, future=True, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
            autoflush=False,
        )

    async def init_models(self) -> None:
        if self.engine is None:
            raise RuntimeError("Database engine has not been configured.")
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        if self.engine is not None:
            await self.engine.dispose()
            self.engine = None
            self.session_factory = None

    async def session(self) -> AsyncIterator[AsyncSession]:
        if self.session_factory is None:
            raise RuntimeError("Database session factory has not been configured.")
        async with self.session_factory() as session:
            yield session


database = Database()


async def get_session() -> AsyncIterator[AsyncSession]:
    async for session in database.session():
        yield session

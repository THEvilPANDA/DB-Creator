import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

import app.models  # noqa: F401 — registers all table metadata
from app.config import settings
from app.database import get_session
from app.main import app


@pytest.fixture(scope="function")
async def test_engine():
    engine = create_async_engine(settings.TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()




@pytest.fixture
async def db_session(test_engine):
    AsyncTestSession = async_sessionmaker(test_engine, expire_on_commit=False)
    async with AsyncTestSession() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(test_engine):
    """Client fixture for async tests."""
    AsyncTestSession = async_sessionmaker(test_engine, expire_on_commit=False)
    session = AsyncTestSession()
    try:
        async def override_get_session():
            yield session

        app.dependency_overrides[get_session] = override_get_session
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        await session.rollback()
        await session.close()

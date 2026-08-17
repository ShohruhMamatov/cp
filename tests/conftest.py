import asyncio
import sys

# psycopg's async mode requires a selector-based loop; Windows defaults to
# ProactorEventLoop. uvicorn already does this switch internally, which is why
# the app runs fine but pytest-asyncio needs it set explicitly.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_session
from app.main import app

# Same server, separate database — never point this at your dev DB.
TEST_DB_URL = settings.database_url.rsplit("/", 1)[0] + "/pm_test"


@pytest_asyncio.fixture
async def engine():
    # NullPool: each test gets a fresh event loop, and pooled connections
    # created on a previous loop raise "attached to a different loop".
    engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine):
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session


@pytest_asyncio.fixture
async def client(session, tmp_path, monkeypatch):
    # Redirect uploads into a per-test temp directory.
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))

    # The whole app now uses the test session — no route code changes.
    app.dependency_overrides[get_session] = lambda: session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
def register(client):
    """Register a user and return their Authorization header."""

    async def _register(login: str, password: str = "password123") -> dict[str, str]:
        await client.post(
            "/auth",
            json={"login": login, "password": password, "password_repeat": password},
        )
        resp = await client.post("/login", json={"login": login, "password": password})
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    return _register


@pytest_asyncio.fixture
async def alice(register):
    return await register("alice")


@pytest_asyncio.fixture
async def bob(register):
    return await register("bob")


@pytest_asyncio.fixture
async def project(client, alice):
    resp = await client.post(
        "/projects", json={"name": "Test Project", "description": "hello"}, headers=alice
    )
    return resp.json()

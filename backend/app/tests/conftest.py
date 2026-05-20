import pytest
from fastapi.testclient import TestClient

from app.database.database import engine
from app.database.models import Base
from app.main import app
from app.storage.memory import store


@pytest.fixture(autouse=True)
def reset_database() -> None:
    import asyncio

    async def _reset() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_reset())
    store.reset()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


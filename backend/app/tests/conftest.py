import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage.memory import store


@pytest.fixture(autouse=True)
def reset_store() -> None:
    store.reset()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


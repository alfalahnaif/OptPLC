"""Hermetic backend test setup (plan item P0-04).

The environment overrides below run before any `app` import, so the settings
singleton and the SQLAlchemy engine bind to a throwaway database and never to
backend/plcforge.db. Every test also gets a fake LLM provider, a fake RAG
service, a temporary benchmark-results directory, and a socket guard that
blocks non-loopback connections.
"""

import asyncio
import os
import shutil
import socket
import tempfile
from pathlib import Path

_TEST_ROOT = Path(tempfile.mkdtemp(prefix="optplc-tests-"))
_TEST_DB = _TEST_ROOT / "test.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB.as_posix()}"
os.environ["LLM_PROVIDER"] = "ollama"  # needs no API key; the client itself is replaced by FakeLLMProvider
os.environ["OLLAMA_BASE_URL"] = "http://127.0.0.1:9"  # unreachable even if a call bypassed the fake

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402

if Path(settings.database_url.split("///", 1)[-1]).resolve() != _TEST_DB.resolve():
    pytest.exit(
        f"Refusing to run tests: DATABASE_URL resolves to {settings.database_url!r}, not the temporary test database.",
        returncode=2,
    )

from app.agents import llm_client  # noqa: E402
from app.database.database import engine  # noqa: E402
from app.database.models import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.services import benchmark_runner, rag_service  # noqa: E402
from app.storage.memory import store  # noqa: E402
from app.tests.fakes import FakeLLMProvider, FakeRAGService  # noqa: E402

_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex


def _loopback_only(real):
    def guarded(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if host not in _LOOPBACK_HOSTS:
            raise RuntimeError(f"Network access is blocked in tests: {address!r}")
        return real(self, address)

    return guarded


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    # asyncio on Windows builds its self-pipe from a loopback socket pair, so loopback stays open.
    monkeypatch.setattr(socket.socket, "connect", _loopback_only(_real_connect))
    monkeypatch.setattr(socket.socket, "connect_ex", _loopback_only(_real_connect_ex))


@pytest.fixture(autouse=True)
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> FakeLLMProvider:
    provider = FakeLLMProvider()
    monkeypatch.setattr(llm_client, "get_llm_client", lambda: provider)
    return provider


@pytest.fixture(autouse=True)
def fake_rag(monkeypatch: pytest.MonkeyPatch) -> FakeRAGService:
    service = FakeRAGService()
    monkeypatch.setattr(rag_service, "get_rag_service", lambda: service)
    return service


@pytest.fixture(autouse=True)
def isolated_benchmark_results(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    results_dir = tmp_path / "benchmark_results"
    monkeypatch.setattr(benchmark_runner.BenchmarkRunner, "RESULTS_DIR", results_dir)
    return results_dir


@pytest.fixture(autouse=True)
def reset_database() -> None:
    async def _reset() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_reset())
    store.reset()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    asyncio.run(engine.dispose())
    shutil.rmtree(_TEST_ROOT, ignore_errors=True)

import asyncio

from app.database.database import AsyncSessionLocal, engine
from app.database.models import Base
from app.database.repository import Repository


def test_tables_can_be_created_from_metadata() -> None:
    async def _run() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_run())


def test_session_model_includes_validation_report_column() -> None:
    columns = {column.name for column in Base.metadata.tables["sessions"].columns}
    assert "validation_report" in columns


def test_repository_persists_and_reads_validation_report() -> None:
    async def _run() -> None:
        repo = Repository()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        async with AsyncSessionLocal() as db:
            await repo.create_project(
                db,
                {
                    "id": "PRJ-9000",
                    "name": "Schema Test Project",
                    "domain": "Testing",
                    "description": "Schema-level persistence validation.",
                    "standard": "IEC 61131-3",
                    "target_language": "Structured Text",
                    "complexity_tier": "simple",
                    "status": "draft",
                },
            )
            session = await repo.create_session(
                db,
                {
                    "id": "PRJ-9000-session-1",
                    "project_id": "PRJ-9000",
                    "state": "validated",
                    "validation_report": {"status": "VERIFIED", "validator": "static.v1"},
                },
            )
            await db.commit()

            fetched = await repo.get_session(db, session.id)
            assert fetched is not None
            assert fetched.validation_report is not None
            assert fetched.validation_report["status"] == "VERIFIED"

    asyncio.run(_run())

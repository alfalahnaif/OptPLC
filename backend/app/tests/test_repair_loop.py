import asyncio

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.repair_service as repair_module
from app.agents import CodeGenerationAgent, PlanningAgent
from app.database.database import AsyncSessionLocal
from app.database.repository import Repository
from app.services.repair_service import RepairService

def test_repair_loop_returns_immediately_when_code_is_verified() -> None:
    async def _run() -> None:
        async with AsyncSessionLocal() as db:
            repo = Repository()
            _, artifact = await save_plan_and_artifact(db, repo, "Motor Control")

            report = await RepairService(db).run_repair_loop("PRJ-0421")

            assert report.finalStatus == "CHECKS_PASSED"
            assert report.iterations == 1
            assert report.debuggingReports == []
            assert report.finalCodeArtifact.artifactId == artifact.artifactId
            assert report.finalValidationReport.status == "CHECKS_PASSED"

    asyncio.run(_run())


def test_motor_missing_emergency_stop_is_repaired_and_verified() -> None:
    async def _run() -> None:
        async with AsyncSessionLocal() as db:
            repo = Repository()
            _, artifact = await save_plan_and_artifact(db, repo, "Motor Control")
            unsafe_source = """PROGRAM Motor_Controller
VAR_INPUT
    Start_PB : BOOL;
    Stop_PB : BOOL;
    E_Stop : BOOL;
    Overload : BOOL;
    Reset_PB : BOOL;
END_VAR
VAR_OUTPUT
    Motor_Run : BOOL;
    Fault_Lamp : BOOL;
    Ready_Lamp : BOOL;
END_VAR
VAR
    Run_Cmd : BOOL;
END_VAR
IF Start_PB AND NOT Stop_PB THEN
    Run_Cmd := TRUE;
END_IF;
Motor_Run := Run_Cmd;
Fault_Lamp := FALSE;
Ready_Lamp := NOT Motor_Run;
END_PROGRAM"""
            await set_code_artifact(
                db,
                repo,
                "PRJ-0421",
                artifact.model_copy(update={"source": unsafe_source}),
            )

            report = await RepairService(db).run_repair_loop("PRJ-0421")

            assert report.finalStatus == "CHECKS_PASSED"
            assert report.iterations == 2
            assert report.debuggingReports[0].errorType == "motor_safety_shutdown"
            assert report.finalCodeArtifact.metadata.generator == "template_based.repair.v1"
            assert "Safety_OK := Emergency_Stop AND NOT Overload;" in report.finalCodeArtifact.source

    asyncio.run(_run())


def test_traffic_light_conflict_is_repaired() -> None:
    async def _run() -> None:
        async with AsyncSessionLocal() as db:
            repo = Repository()
            _, artifact = await save_plan_and_artifact(db, repo, "Traffic Control")
            unsafe_source = """PROGRAM Traffic_Controller
VAR_INPUT
    Vehicle_Detect : BOOL;
    Ped_Request : BOOL;
    Emergency_Flash : BOOL;
    Cycle_Timer : TIME;
END_VAR
VAR_OUTPUT
    Red_Light : BOOL;
    Amber_Light : BOOL;
    Green_Light : BOOL;
    Ped_Walk : BOOL;
END_VAR
Green_Light := TRUE;
Ped_Walk := TRUE;
Red_Light := FALSE;
Amber_Light := FALSE;
END_PROGRAM"""
            await set_code_artifact(
                db,
                repo,
                "PRJ-0421",
                artifact.model_copy(update={"source": unsafe_source}),
            )

            report = await RepairService(db).run_repair_loop("PRJ-0421")

            assert report.finalStatus == "CHECKS_PASSED"
            assert report.debuggingReports[0].errorType == "traffic_conflicting_green"
            assert "Green_Light := NOT Red_Light AND NOT Amber_Light;" in report.finalCodeArtifact.source

    asyncio.run(_run())


def test_invalid_syntax_triggers_debugging_and_regeneration() -> None:
    async def _run() -> None:
        async with AsyncSessionLocal() as db:
            repo = Repository()
            _, artifact = await save_plan_and_artifact(db, repo, "Motor Control")
            await set_code_artifact(
                db,
                repo,
                "PRJ-0421",
                artifact.model_copy(update={"source": artifact.source.replace("END_PROGRAM", "")}),
            )

            report = await RepairService(db).run_repair_loop("PRJ-0421")

            assert report.finalStatus == "CHECKS_PASSED"
            assert report.validationReports[0].status == "SYNTAX_ERROR"
            assert report.debuggingReports[0].errorType == "missing_end_pou"
            assert "END_PROGRAM" in report.finalCodeArtifact.source

    asyncio.run(_run())


def test_max_iter_stops_infinite_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _run() -> None:
        async with AsyncSessionLocal() as db:
            repo = Repository()
            _, artifact = await save_plan_and_artifact(db, repo, "Motor Control")
            await set_code_artifact(
                db,
                repo,
                "PRJ-0421",
                artifact.model_copy(update={"source": artifact.source.replace("END_PROGRAM", "")}),
            )

            class AlwaysBadGenerator:
                def __init__(self, mode: str = "template_based") -> None:
                    self.mode = mode

                async def generate_code(self, **kwargs):
                    repaired = await CodeGenerationAgent(mode="template_based").generate_code(**kwargs)
                    return repaired.model_copy(update={"source": repaired.source.replace("END_PROGRAM", "")})

            monkeypatch.setattr(repair_module, "CodeGenerationAgent", AlwaysBadGenerator)

            report = await RepairService(db).run_repair_loop("PRJ-0421", max_iter=2)

            assert report.finalStatus == "ITERATION_LIMIT_REACHED"
            assert report.iterations == 2
            assert report.finalValidationReport.status == "SYNTAX_ERROR"

    asyncio.run(_run())


def test_repair_loop_report_is_stored_in_repository() -> None:
    async def _run() -> None:
        async with AsyncSessionLocal() as db:
            repo = Repository()
            await save_plan_and_artifact(db, repo, "Motor Control")

            report = await RepairService(db).run_repair_loop("PRJ-0421")

            session = await repo.get_latest_session_for_project(db, "PRJ-0421")
            assert session is not None
            assert session.repair_loop_report is not None
            assert session.repair_loop_report["projectId"] == report.projectId
            assert session.repair_loop_report["finalStatus"] == "CHECKS_PASSED"

    asyncio.run(_run())


async def save_plan_and_artifact(db: AsyncSession, repo: Repository, domain: str):
    requirements = {
        "Motor Control": "Motor start stop with emergency stop and overload protection.",
        "Traffic Control": "Traffic light controller with pedestrian request.",
    }
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-0421",
        requirement_text=requirements.get(domain, "Generic PLC control requirement."),
        domain=domain,
    )
    artifact = await CodeGenerationAgent().generate_code(project_id="PRJ-0421", plan=plan)
    await repo.create_project(
        db,
        {
            "id": "PRJ-0421",
            "name": "Repair Loop Test Project",
            "domain": domain,
            "description": "Repository-backed repair loop tests.",
            "standard": "IEC 61131-3",
            "target_language": "Structured Text",
            "complexity_tier": "medium",
            "status": "generated",
        },
    )
    await repo.create_session(
        db,
        {
            "id": "PRJ-0421-session-1",
            "project_id": "PRJ-0421",
            "state": "generated",
            "plan_object": plan.model_dump(),
            "code_artifact": artifact.model_dump(),
            "code_artifact_history": [artifact.model_dump()],
            "st_code": artifact.source,
        },
    )
    await db.commit()
    return plan, artifact


async def set_code_artifact(db: AsyncSession, repo: Repository, project_id: str, artifact: object) -> None:
    session = await repo.get_or_create_project_session(db, project_id)
    await repo.update_session_state(
        db,
        session.id,
        session.state,
        code_artifact=artifact.model_dump(),
        code_artifact_history=[artifact.model_dump()],
        st_code=artifact.source,
    )
    await db.commit()

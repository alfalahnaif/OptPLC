"""Evidence levels and the VERIFIED rename (P1-04, D-033).

CHECKS_PASSED says the checks passed; evidenceLevel says what they rest on. Only an unmodified
MATIEC compile is L1, and the parser check (parser.v1) never rises above L0 (D-029).
"""

import asyncio
import json
from typing import get_args

from fastapi.testclient import TestClient

from app.agents import ValidationAgent
from app.database.database import AsyncSessionLocal
from app.database.models import SessionModel
from app.schemas.contracts import RepairLoopFinalStatus, RepairLoopReport, ValidationReport, ValidationStatus
from app.tests.test_optimization_agent import create_project, submit_requirements
from app.tests.test_validation_agent import StubMatiecValidator, _motor_plan_and_artifact

MATIEC_PASSED = {"method": "matiec", "passed": True, "errors": [], "return_code": 0}
MATIEC_FAILED = {"method": "matiec", "passed": False, "errors": ["matiec: syntax error near END_IF"], "return_code": 1}
MATIEC_MISSING = {"method": "unavailable", "passed": None, "errors": [], "reason": "missing binary"}


def test_the_contracts_no_longer_offer_verified() -> None:
    assert "VERIFIED" not in get_args(get_args(ValidationStatus)[0])
    assert "VERIFIED" not in get_args(get_args(RepairLoopFinalStatus)[0])


async def test_a_matiec_compile_with_passing_rules_is_l2() -> None:
    plan, artifact = await _motor_plan_and_artifact()

    report = ValidationAgent(matiec_validator=StubMatiecValidator(MATIEC_PASSED)).validate(
        project_id="PRJ-MOTOR", artifact=artifact, plan=plan
    )

    assert report.status == "CHECKS_PASSED"
    assert report.evidenceLevel == "STATIC_RULES_PASSED"


async def test_a_matiec_compile_with_a_failing_rule_stays_at_l1() -> None:
    plan, artifact = await _motor_plan_and_artifact()
    start_dominant = artifact.source.replace("ELSIF Start_Edge.Q THEN", "END_IF;\nIF Start_Edge.Q THEN")
    assert start_dominant != artifact.source

    report = ValidationAgent(matiec_validator=StubMatiecValidator(MATIEC_PASSED)).validate(
        project_id="PRJ-MOTOR", artifact=artifact.model_copy(update={"source": start_dominant}), plan=plan
    )

    assert report.status == "FORMAL_VIOLATION"
    assert report.evidenceLevel == "COMPILES"


async def test_a_failed_compile_is_l0() -> None:
    plan, artifact = await _motor_plan_and_artifact()

    report = ValidationAgent(matiec_validator=StubMatiecValidator(MATIEC_FAILED)).validate(
        project_id="PRJ-MOTOR", artifact=artifact, plan=plan
    )

    assert report.status == "SYNTAX_ERROR"
    assert report.evidenceLevel == "GENERATED"


async def test_the_parser_check_never_rises_above_l0() -> None:
    plan, artifact = await _motor_plan_and_artifact()

    report = ValidationAgent(matiec_validator=StubMatiecValidator(MATIEC_MISSING)).validate(
        project_id="PRJ-MOTOR", artifact=artifact, plan=plan
    )

    assert report.status == "CHECKS_PASSED"
    assert report.validator == "parser.v1"
    assert report.evidenceLevel == "GENERATED"
    assert "not been compiled" in report.summary


async def test_stored_verified_reports_read_as_checks_passed_at_l0() -> None:
    plan, artifact = await _motor_plan_and_artifact()
    current = ValidationAgent(matiec_validator=StubMatiecValidator(MATIEC_PASSED)).validate(
        project_id="PRJ-MOTOR", artifact=artifact, plan=plan
    )
    stored = current.model_dump()
    stored["status"] = "VERIFIED"
    del stored["evidenceLevel"]
    loop = RepairLoopReport(
        projectId="PRJ-MOTOR",
        finalStatus="CHECKS_PASSED",
        iterations=1,
        finalCodeArtifact=artifact,
        finalValidationReport=current,
        debuggingReports=[],
        codeVersions=[artifact],
        validationReports=[current],
        summary="Stored before D-033.",
    ).model_dump()
    loop["finalStatus"] = "VERIFIED"
    loop["validationReports"] = [stored]

    report = ValidationReport.model_validate(stored)
    restored_loop = RepairLoopReport.model_validate(loop)

    assert report.status == "CHECKS_PASSED"
    # The old compile may predate D-005, so the stored fields cannot support a higher level.
    assert report.evidenceLevel == "GENERATED"
    assert restored_loop.finalStatus == "CHECKS_PASSED"
    assert restored_loop.validationReports[0].status == "CHECKS_PASSED"


def test_a_stored_verified_validation_still_unlocks_optimization(client: TestClient) -> None:
    project_id = create_project(client)
    submit_requirements(client, project_id)
    client.post(f"/api/projects/{project_id}/plan")
    client.post(f"/api/projects/{project_id}/generate")
    client.post(f"/api/projects/{project_id}/validate")

    async def _store_as_before_d033() -> None:
        async with AsyncSessionLocal() as session:
            row = (await session.execute(SessionModel.__table__.select())).mappings().first()
            assert row is not None
            legacy = dict(row["validation_report"])
            legacy["status"] = "VERIFIED"
            legacy.pop("evidenceLevel")
            columns = {key: legacy for key in ("validation_report", "validation_result") if key in row}
            await session.execute(
                SessionModel.__table__.update().where(SessionModel.id == row["id"]).values(**columns)
            )
            await session.commit()

    asyncio.run(_store_as_before_d033())

    validation = client.get(f"/api/projects/{project_id}/validation").json()
    assert validation["status"] == "CHECKS_PASSED"
    assert validation["evidenceLevel"] == "GENERATED"
    assert client.post(f"/api/projects/{project_id}/optimize").status_code == 200


def test_the_final_report_states_the_evidence_level_and_the_safety_scope(client: TestClient) -> None:
    project_id = create_project(client)
    submit_requirements(client, project_id)
    client.post(f"/api/projects/{project_id}/plan")
    client.post(f"/api/projects/{project_id}/generate")
    client.post(f"/api/projects/{project_id}/validate")

    report = client.get(f"/api/projects/{project_id}/report").json()

    level = report["validation"]["evidenceLevel"]
    assert f"evidence level {level}" in report["finalStatusSummary"]
    assert "out of scope" in report["limitationsDisclaimer"]
    assert "not formal verification" in report["limitationsDisclaimer"]
    # G1: nothing below L4 may be called verified.
    assert "verified" not in json.dumps(report).lower()

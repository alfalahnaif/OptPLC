import pytest
from fastapi.testclient import TestClient
import asyncio

from app.agents import CodeGenerationAgent, OptimizationAgent, PlanningAgent, ValidationAgent
from app.database.database import AsyncSessionLocal
from app.database.models import SessionModel
from app.schemas.contracts import CodeArtifact, CodeMetadata, CodeMetrics
from app.services.metrics_service import MetricsService
from app.storage.memory import store


def test_optimization_fails_with_400_if_no_code_artifact_exists(client: TestClient) -> None:
    project_id = create_project(client)
    submit_requirements(client, project_id)
    client.post(f"/api/projects/{project_id}/plan")

    response = client.post(f"/api/projects/{project_id}/optimize")

    assert response.status_code == 400
    assert response.json()["detail"] == "CodeArtifact must be generated before optimization."


def test_optimization_fails_with_400_if_no_plan_object_exists(client: TestClient) -> None:
    project_id = create_project(client)

    response = client.post(f"/api/projects/{project_id}/optimize")

    assert response.status_code == 400
    assert response.json()["detail"] == "PlanObject must be generated before optimization."


def test_optimization_fails_with_400_if_no_validation_report_exists(client: TestClient) -> None:
    project_id = create_project(client)
    submit_requirements(client, project_id)
    client.post(f"/api/projects/{project_id}/plan")
    client.post(f"/api/projects/{project_id}/generate")

    response = client.post(f"/api/projects/{project_id}/optimize")

    assert response.status_code == 400
    assert response.json()["detail"] == "ValidationReport must be generated before optimization."


def test_optimization_fails_with_400_if_code_is_not_verified(client: TestClient) -> None:
    project_id = create_project(client)
    submit_requirements(client, project_id)
    client.post(f"/api/projects/{project_id}/plan")
    client.post(f"/api/projects/{project_id}/generate")

    async def _corrupt_artifact() -> None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(SessionModel.__table__.select())
            row = result.mappings().first()
            assert row is not None
            artifact = row["code_artifact"]
            artifact["source"] = artifact["source"].replace("END_PROGRAM", "")
            history = row["code_artifact_history"]
            if history:
                history[-1] = artifact
            await session.execute(
                SessionModel.__table__.update()
                .where(SessionModel.id == row["id"])
                .values(code_artifact=artifact, code_artifact_history=history)
            )
            await session.commit()

    asyncio.run(_corrupt_artifact())
    client.post(f"/api/projects/{project_id}/validate")

    response = client.post(f"/api/projects/{project_id}/optimize")

    assert response.status_code == 400
    assert response.json()["detail"] == "Code must be verified before optimization. Run validation or repair loop first."


def test_verified_motor_code_optimizes_and_remains_verified(client: TestClient) -> None:
    project_id = create_project(client)
    submit_requirements(client, project_id)
    client.post(f"/api/projects/{project_id}/plan")
    client.post(f"/api/projects/{project_id}/generate")
    client.post(f"/api/projects/{project_id}/validate")

    response = client.post(f"/api/projects/{project_id}/optimize")

    assert response.status_code == 200
    report = response.json()
    assert report["status"] == "OPTIMIZED"
    assert report["optimizer"] == "static.v1"
    assert report["revalidationStatus"] == "VERIFIED"
    assert report["optimizedCode"]["metadata"]["generator"] == "static_optimizer.v1"
    assert {item["name"] for item in report["passes"]} == {
        "Structural Simplification",
        "Logic Compaction",
        "Maintainability Enhancement",
    }


async def test_optimization_metrics_improve_or_stay_equal() -> None:
    plan, artifact = await save_verified_motor_inputs()
    validation = store.get_validation_report("PRJ-0421")
    assert validation is not None

    report = await OptimizationAgent().optimize(
        project_id="PRJ-0421",
        artifact=artifact,
        plan=plan,
        validation=validation,
    )

    assert report.status != "CANNOT_OPTIMIZE"  # otherwise the metric comparisons below pass vacuously
    assert report.afterMetrics.loc <= report.beforeMetrics.loc
    assert report.afterMetrics.cyclomaticComplexity <= report.beforeMetrics.cyclomaticComplexity
    assert report.afterMetrics.maintainabilityIndex >= report.beforeMetrics.maintainabilityIndex
    assert report.afterMetrics.estimatedScanTimeMs <= report.beforeMetrics.estimatedScanTimeMs


async def test_rollback_occurs_if_optimization_pass_breaks_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    plan, artifact = await save_verified_motor_inputs()
    validation = store.get_validation_report("PRJ-0421")
    assert validation is not None

    def broken_logic_compaction(source: str, _plan) -> tuple[str, str]:
        return source.replace("END_PROGRAM", ""), "Compaction that drops END_PROGRAM."

    monkeypatch.setattr(OptimizationAgent, "_logic_compaction", staticmethod(broken_logic_compaction))

    report = await OptimizationAgent().optimize(
        project_id="PRJ-0421",
        artifact=artifact,
        plan=plan,
        validation=validation,
    )

    assert any(event.passName == "Logic Compaction" for event in report.rollbackEvents)
    assert any(item.name == "Logic Compaction" and item.status == "rolled_back" for item in report.passes)
    assert report.revalidationStatus == "VERIFIED"


def test_optimization_report_is_stored_in_memory(client: TestClient) -> None:
    project_id = create_project(client)
    submit_requirements(client, project_id)
    client.post(f"/api/projects/{project_id}/plan")
    client.post(f"/api/projects/{project_id}/generate")
    client.post(f"/api/projects/{project_id}/validate")

    response = client.post(f"/api/projects/{project_id}/optimize")

    assert response.status_code == 200
    body = response.json()

    async def _has_optimization_report() -> bool:
        async with AsyncSessionLocal() as session:
            result = await session.execute(SessionModel.__table__.select())
            row = result.mappings().first()
            return bool(row and row["optimization_report"] and row["code_artifact"]["artifactId"] == body["optimizedArtifactId"])

    assert asyncio.run(_has_optimization_report()) is True


async def test_llm_mode_keeps_code_unchanged_when_replies_are_unusable(fake_llm) -> None:
    plan, artifact = await save_verified_motor_inputs()
    validation = store.get_validation_report("PRJ-0421")
    assert validation is not None

    report = await OptimizationAgent(mode="llm").optimize(
        project_id="PRJ-0421",
        artifact=artifact,
        plan=plan,
        validation=validation,
    )

    assert report.status == "NO_CHANGES"
    assert report.optimizedCode.source == artifact.source
    assert len(fake_llm.calls) == 3  # one reply per optimization pass


def test_metrics_service_counts_structured_text_operations() -> None:
    metrics = MetricsService.calculate(
        """
PROGRAM P
VAR_INPUT
    A : BOOL;
END_VAR
VAR_OUTPUT
    B : BOOL;
END_VAR
IF A THEN
    B := TRUE;
END_IF;
END_PROGRAM
"""
    )

    assert metrics.loc == 3
    assert metrics.cyclomaticComplexity == 2
    assert metrics.estimatedScanTimeMs > 0


async def save_verified_motor_inputs(save_validation: bool = True):
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-0421",
        requirement_text="Motor start stop with emergency stop and overload protection.",
        domain="Motor Control",
    )
    artifact = await CodeGenerationAgent().generate_code(project_id="PRJ-0421", plan=plan)
    store.save_plan("PRJ-0421", plan)
    store.save_code_artifact("PRJ-0421", artifact)
    if save_validation:
        store.save_validation_report(
            "PRJ-0421",
            ValidationAgent().validate(project_id="PRJ-0421", artifact=artifact, plan=plan),
        )
    return plan, artifact


def create_project(client: TestClient) -> str:
    response = client.post(
        "/api/projects",
        json={
            "name": "Motor Control - Conveyor M-12",
            "description": "Motor control with safety.",
            "domain": "Motor Control",
            "targetLanguage": "Structured Text",
            "complexityTier": "medium",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def submit_requirements(client: TestClient, project_id: str) -> None:
    response = client.post(
        f"/api/projects/{project_id}/requirements",
        json={
            "projectId": project_id,
            "text": "Motor start stop with emergency stop and overload protection.",
            "safetyConstraints": ["Motor must not auto-restart after E-Stop"],
            "performanceTargets": {
                "maxScanTimeMs": 5,
                "maxCyclomaticComplexity": 8,
                "minMaintainabilityIndex": 75,
                "maxIterations": 5,
            },
        },
    )
    assert response.status_code == 200


def minimal_artifact(project_id: str) -> CodeArtifact:
    return CodeArtifact(
        projectId=project_id,
        artifactId=f"{project_id}-manual-code",
        language="structured-text",
        filename="manual.st",
        source="PROGRAM Manual\nVAR_INPUT\n    A : BOOL;\nEND_VAR\nVAR_OUTPUT\n    B : BOOL;\nEND_VAR\nB := A;\nEND_PROGRAM",
        iteration=1,
        generatedAt="2026-05-19T10:00:00Z",
        metrics=CodeMetrics(loc=1, cyclomaticComplexity=1, maintainabilityIndex=95),
        metadata=CodeMetadata(
            generator="manual-test",
            iecStandard="IEC 61131-3",
            sourcePlanId=project_id,
            createdAt="2026-05-19T10:00:00Z",
            iteration=1,
        ),
    )

import pytest
from fastapi.testclient import TestClient

from app.agents import CodeGenerationAgent, OptimizationAgent, PlanningAgent, ValidationAgent
from app.schemas.contracts import CodeArtifact, CodeMetadata, CodeMetrics
from app.services.metrics_service import MetricsService
from app.storage.memory import store


def test_optimization_fails_with_400_if_no_code_artifact_exists(client: TestClient) -> None:
    client.post("/api/projects/PRJ-0421/plan")

    response = client.post("/api/projects/PRJ-0421/optimize")

    assert response.status_code == 400
    assert response.json()["detail"] == "CodeArtifact must be generated before optimization."


def test_optimization_fails_with_400_if_no_plan_object_exists(client: TestClient) -> None:
    store.save_code_artifact("PRJ-0421", minimal_artifact("PRJ-0421"))

    response = client.post("/api/projects/PRJ-0421/optimize")

    assert response.status_code == 400
    assert response.json()["detail"] == "PlanObject must be generated before optimization."


def test_optimization_fails_with_400_if_no_validation_report_exists(client: TestClient) -> None:
    save_verified_motor_inputs(save_validation=False)

    response = client.post("/api/projects/PRJ-0421/optimize")

    assert response.status_code == 400
    assert response.json()["detail"] == "ValidationReport must be generated before optimization."


def test_optimization_fails_with_400_if_code_is_not_verified(client: TestClient) -> None:
    plan, artifact = save_verified_motor_inputs(save_validation=False)
    unsafe_artifact = artifact.model_copy(
        update={
            "source": artifact.source.replace("Motor_Run := Run_Cmd AND Safety_OK AND NOT Fault_State;", "Motor_Run := Run_Cmd;")
        }
    )
    store.save_code_artifact("PRJ-0421", unsafe_artifact)
    store.save_validation_report(
        "PRJ-0421",
        ValidationAgent().validate(project_id="PRJ-0421", artifact=unsafe_artifact, plan=plan),
    )

    response = client.post("/api/projects/PRJ-0421/optimize")

    assert response.status_code == 400
    assert response.json()["detail"] == "Code must be verified before optimization. Run validation or repair loop first."


def test_verified_motor_code_optimizes_and_remains_verified(client: TestClient) -> None:
    client.post("/api/projects/PRJ-0421/plan")
    client.post("/api/projects/PRJ-0421/generate")
    client.post("/api/projects/PRJ-0421/validate")

    response = client.post("/api/projects/PRJ-0421/optimize")

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


def test_optimization_metrics_improve_or_stay_equal() -> None:
    plan, artifact = save_verified_motor_inputs()
    validation = store.get_validation_report("PRJ-0421")
    assert validation is not None

    report = OptimizationAgent().optimize(
        project_id="PRJ-0421",
        artifact=artifact,
        plan=plan,
        validation=validation,
    )

    assert report.afterMetrics.loc <= report.beforeMetrics.loc
    assert report.afterMetrics.cyclomaticComplexity <= report.beforeMetrics.cyclomaticComplexity
    assert report.afterMetrics.maintainabilityIndex >= report.beforeMetrics.maintainabilityIndex
    assert report.afterMetrics.estimatedScanTimeMs <= report.beforeMetrics.estimatedScanTimeMs


def test_rollback_occurs_if_optimization_pass_breaks_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    plan, artifact = save_verified_motor_inputs()
    validation = store.get_validation_report("PRJ-0421")
    assert validation is not None

    def broken_logic_compaction(source: str, _plan) -> tuple[str, str]:
        return source.replace("Motor_Run := Run_Cmd AND Safety_OK AND NOT Fault_State;", "Motor_Run := Run_Cmd;"), "Unsafe compaction."

    monkeypatch.setattr(OptimizationAgent, "_logic_compaction", staticmethod(broken_logic_compaction))

    report = OptimizationAgent().optimize(
        project_id="PRJ-0421",
        artifact=artifact,
        plan=plan,
        validation=validation,
    )

    assert any(event.passName == "Logic Compaction" for event in report.rollbackEvents)
    assert any(item.name == "Logic Compaction" and item.status == "rolled_back" for item in report.passes)
    assert report.revalidationStatus == "VERIFIED"


def test_optimization_report_is_stored_in_memory(client: TestClient) -> None:
    client.post("/api/projects/PRJ-0421/plan")
    client.post("/api/projects/PRJ-0421/generate")
    client.post("/api/projects/PRJ-0421/validate")

    response = client.post("/api/projects/PRJ-0421/optimize")

    assert response.status_code == 200
    stored = store.get_optimization_report("PRJ-0421")
    assert stored is not None
    assert stored.projectId == "PRJ-0421"
    assert stored.optimizer == "static.v1"
    assert store.get_code_artifact("PRJ-0421") is not None
    assert store.get_code_artifact("PRJ-0421").artifactId == stored.optimizedArtifactId


def test_llm_mode_raises_not_implemented() -> None:
    plan, artifact = save_verified_motor_inputs()
    validation = store.get_validation_report("PRJ-0421")
    assert validation is not None

    with pytest.raises(NotImplementedError, match="llm mode"):
        OptimizationAgent(mode="llm").optimize(
            project_id="PRJ-0421",
            artifact=artifact,
            plan=plan,
            validation=validation,
        )


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


def save_verified_motor_inputs(save_validation: bool = True):
    plan = PlanningAgent().generate_plan(
        project_id="PRJ-0421",
        requirement_text="Motor start stop with emergency stop and overload protection.",
        domain="Motor Control",
    )
    artifact = CodeGenerationAgent().generate_code(project_id="PRJ-0421", plan=plan)
    store.save_plan("PRJ-0421", plan)
    store.save_code_artifact("PRJ-0421", artifact)
    if save_validation:
        store.save_validation_report(
            "PRJ-0421",
            ValidationAgent().validate(project_id="PRJ-0421", artifact=artifact, plan=plan),
        )
    return plan, artifact


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

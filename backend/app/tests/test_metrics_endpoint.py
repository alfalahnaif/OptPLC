from fastapi.testclient import TestClient

from app.agents import CodeGenerationAgent, PlanningAgent
from app.services.repair_service import RepairService
from app.storage.memory import store


def test_metrics_endpoint_returns_400_if_no_code_artifact_exists(client: TestClient) -> None:
    client.post("/api/projects/PRJ-0421/plan")

    response = client.get("/api/projects/PRJ-0421/metrics")

    assert response.status_code == 400
    assert response.json()["detail"] == "CodeArtifact must be generated before metrics can be computed."


def test_metrics_for_generated_only_project_returns_same_before_after(client: TestClient) -> None:
    client.post("/api/projects/PRJ-0421/plan")
    client.post("/api/projects/PRJ-0421/generate")

    response = client.get("/api/projects/PRJ-0421/metrics")

    assert response.status_code == 200
    report = response.json()
    assert report["source"]["selected"] == "generated_code"
    assert report["beforeMetrics"] == report["afterMetrics"]
    assert report["metricsDelta"]["locDelta"] == 0
    assert report["metricsDelta"]["cyclomaticComplexityDelta"] == 0
    assert report["metricsDelta"]["maintainabilityIndexDelta"] == 0
    assert report["metricsDelta"]["estimatedScanTimeDelta"] == 0


def test_metrics_after_repair_loop_uses_repaired_code_as_after_metrics(client: TestClient) -> None:
    plan = PlanningAgent().generate_plan(
        project_id="PRJ-0421",
        requirement_text="Motor start stop with emergency stop and overload protection.",
        domain="Motor Control",
    )
    artifact = CodeGenerationAgent().generate_code(project_id="PRJ-0421", plan=plan)
    unsafe_source = artifact.source.replace("END_PROGRAM", "")
    store.save_plan("PRJ-0421", plan)
    store.save_code_artifact("PRJ-0421", artifact.model_copy(update={"source": unsafe_source}))

    repair_report = RepairService(store).run_repair_loop("PRJ-0421")
    response = client.get("/api/projects/PRJ-0421/metrics")

    assert response.status_code == 200
    report = response.json()
    assert repair_report.finalStatus == "VERIFIED"
    assert report["source"]["selected"] == "repaired_code"
    assert report["source"]["repairedCode"] == repair_report.finalCodeArtifact.artifactId
    assert report["history"][-1]["source"] == "repaired_code"
    assert report["afterMetrics"]["loc"] > 0


def test_metrics_after_optimization_uses_optimized_code_as_after_metrics(client: TestClient) -> None:
    client.post("/api/projects/PRJ-0421/plan")
    client.post("/api/projects/PRJ-0421/generate")
    client.post("/api/projects/PRJ-0421/validate")
    optimize_response = client.post("/api/projects/PRJ-0421/optimize")

    response = client.get("/api/projects/PRJ-0421/metrics")

    assert optimize_response.status_code == 200
    assert response.status_code == 200
    optimization_report = optimize_response.json()
    report = response.json()
    assert report["source"]["selected"] == "optimized_code"
    assert report["source"]["optimizedCode"] == optimization_report["optimizedArtifactId"]
    assert report["afterMetrics"] == optimization_report["afterMetrics"]
    assert report["latestOptimizationStatus"] == optimization_report["status"]


def test_metrics_delta_fields_are_computed_correctly(client: TestClient) -> None:
    client.post("/api/projects/PRJ-0421/plan")
    client.post("/api/projects/PRJ-0421/generate")
    client.post("/api/projects/PRJ-0421/validate")
    client.post("/api/projects/PRJ-0421/optimize")

    response = client.get("/api/projects/PRJ-0421/metrics")

    assert response.status_code == 200
    report = response.json()
    before = report["beforeMetrics"]
    after = report["afterMetrics"]
    delta = report["metricsDelta"]
    assert delta["locDelta"] == after["loc"] - before["loc"]
    assert delta["cyclomaticComplexityDelta"] == after["cyclomaticComplexity"] - before["cyclomaticComplexity"]
    assert delta["maintainabilityIndexDelta"] == after["maintainabilityIndex"] - before["maintainabilityIndex"]
    assert delta["locReductionPercent"] >= 0
    assert delta["complexityReductionPercent"] >= 0


def test_metrics_report_is_stored_in_memory(client: TestClient) -> None:
    client.post("/api/projects/PRJ-0421/plan")
    client.post("/api/projects/PRJ-0421/generate")

    response = client.get("/api/projects/PRJ-0421/metrics")

    assert response.status_code == 200
    stored = store.get_metrics_report("PRJ-0421")
    assert stored is not None
    assert stored.projectId == "PRJ-0421"
    assert len(store.list_metrics_reports("PRJ-0421")) == 1


def test_metrics_values_are_present_and_numeric(client: TestClient) -> None:
    client.post("/api/projects/PRJ-0421/plan")
    client.post("/api/projects/PRJ-0421/generate")

    response = client.get("/api/projects/PRJ-0421/metrics")

    assert response.status_code == 200
    metrics = response.json()["afterMetrics"]
    assert isinstance(metrics["loc"], int)
    assert isinstance(metrics["cyclomaticComplexity"], int)
    assert isinstance(metrics["maintainabilityIndex"], int)
    assert isinstance(metrics["estimatedScanTimeMs"], float)

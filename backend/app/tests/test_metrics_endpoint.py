from fastapi.testclient import TestClient

from app.database.database import AsyncSessionLocal
from app.database.models import SessionModel


def _create_project(client: TestClient) -> str:
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


def _submit_requirements(client: TestClient, project_id: str, text: str) -> None:
    response = client.post(
        f"/api/projects/{project_id}/requirements",
        json={
            "projectId": project_id,
            "text": text,
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


def test_metrics_endpoint_returns_400_if_no_code_artifact_exists(client: TestClient) -> None:
    project_id = _create_project(client)
    _submit_requirements(client, project_id, "Motor start stop with emergency stop and overload protection.")
    client.post(f"/api/projects/{project_id}/plan")

    response = client.get(f"/api/projects/{project_id}/metrics")

    assert response.status_code == 400
    assert response.json()["detail"] == "CodeArtifact must be generated before metrics can be computed."


def test_metrics_for_generated_only_project_returns_same_before_after(client: TestClient) -> None:
    project_id = _create_project(client)
    _submit_requirements(client, project_id, "Motor start stop with emergency stop and overload protection.")
    client.post(f"/api/projects/{project_id}/plan")
    client.post(f"/api/projects/{project_id}/generate")

    response = client.get(f"/api/projects/{project_id}/metrics")

    assert response.status_code == 200
    report = response.json()
    assert report["source"]["selected"] == "generated_code"
    assert report["beforeMetrics"] == report["afterMetrics"]
    assert report["metricsDelta"]["locDelta"] == 0
    assert report["metricsDelta"]["cyclomaticComplexityDelta"] == 0
    assert report["metricsDelta"]["maintainabilityIndexDelta"] == 0
    assert report["metricsDelta"]["estimatedScanTimeDelta"] == 0


def test_metrics_after_optimization_uses_optimized_code_as_after_metrics(client: TestClient) -> None:
    project_id = _create_project(client)
    _submit_requirements(client, project_id, "Motor start stop with emergency stop and overload protection.")
    client.post(f"/api/projects/{project_id}/plan")
    client.post(f"/api/projects/{project_id}/generate")
    client.post(f"/api/projects/{project_id}/validate")
    optimize_response = client.post(f"/api/projects/{project_id}/optimize")

    response = client.get(f"/api/projects/{project_id}/metrics")

    assert optimize_response.status_code == 200
    assert response.status_code == 200
    optimization_report = optimize_response.json()
    report = response.json()
    assert report["source"]["selected"] == "optimized_code"
    assert report["source"]["optimizedCode"] == optimization_report["optimizedArtifactId"]
    assert report["afterMetrics"] == optimization_report["afterMetrics"]
    assert report["latestOptimizationStatus"] == optimization_report["status"]


def test_metrics_delta_fields_are_computed_correctly(client: TestClient) -> None:
    project_id = _create_project(client)
    _submit_requirements(client, project_id, "Motor start stop with emergency stop and overload protection.")
    client.post(f"/api/projects/{project_id}/plan")
    client.post(f"/api/projects/{project_id}/generate")
    client.post(f"/api/projects/{project_id}/validate")
    client.post(f"/api/projects/{project_id}/optimize")

    response = client.get(f"/api/projects/{project_id}/metrics")

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


def test_metrics_report_is_stored_in_db(client: TestClient) -> None:
    project_id = _create_project(client)
    _submit_requirements(client, project_id, "Motor start stop with emergency stop and overload protection.")
    client.post(f"/api/projects/{project_id}/plan")
    client.post(f"/api/projects/{project_id}/generate")
    response = client.get(f"/api/projects/{project_id}/metrics")

    assert response.status_code == 200

    import asyncio

    async def _has_metrics() -> bool:
        async with AsyncSessionLocal() as session:
            result = await session.execute(SessionModel.__table__.select())
            rows = result.mappings().all()
            return bool(rows and rows[0].get("metrics_report"))

    assert asyncio.run(_has_metrics()) is True


def test_metrics_values_are_present_and_numeric(client: TestClient) -> None:
    project_id = _create_project(client)
    _submit_requirements(client, project_id, "Motor start stop with emergency stop and overload protection.")
    client.post(f"/api/projects/{project_id}/plan")
    client.post(f"/api/projects/{project_id}/generate")

    response = client.get(f"/api/projects/{project_id}/metrics")

    assert response.status_code == 200
    metrics = response.json()["afterMetrics"]
    assert isinstance(metrics["loc"], int)
    assert isinstance(metrics["cyclomaticComplexity"], int)
    assert isinstance(metrics["maintainabilityIndex"], int)
    assert isinstance(metrics["estimatedScanTimeMs"], float)

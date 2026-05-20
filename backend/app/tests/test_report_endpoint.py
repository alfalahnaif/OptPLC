from fastapi.testclient import TestClient

from app.schemas.contracts import FinalReport


def create_project_payload() -> dict:
    return {
        "name": "Final Report Validation Project",
        "description": "Validate final report endpoint behavior.",
        "domain": "Motor Control",
        "targetLanguage": "Structured Text",
        "complexityTier": "medium",
    }


def requirement_payload(project_id: str) -> dict:
    return {
        "projectId": project_id,
        "text": "Control conveyor motor with E-stop and overload protection.",
        "safetyConstraints": [
            "Emergency stop must de-energize motor output in one scan.",
            "No auto restart after fault.",
        ],
        "performanceTargets": {
            "maxScanTimeMs": 5,
            "maxCyclomaticComplexity": 8,
            "minMaintainabilityIndex": 75,
            "maxIterations": 5,
        },
    }


def _create_project(client: TestClient) -> str:
    response = client.post("/api/projects", json=create_project_payload())
    assert response.status_code == 201
    return response.json()["id"]


def test_report_returns_404_for_missing_project(client: TestClient) -> None:
    response = client.get("/api/projects/PRJ-9999/report")
    assert response.status_code == 404


def test_report_returns_400_when_no_artifacts_exist(client: TestClient) -> None:
    project_id = _create_project(client)
    response = client.get(f"/api/projects/{project_id}/report")
    assert response.status_code == 400
    assert "no project artifacts exist yet" in response.json()["detail"]


def test_report_includes_requirement_and_plan_with_missing_indicators(client: TestClient) -> None:
    project_id = _create_project(client)
    client.post(f"/api/projects/{project_id}/requirements", json=requirement_payload(project_id))
    client.post(f"/api/projects/{project_id}/plan")

    response = client.get(f"/api/projects/{project_id}/report")
    assert response.status_code == 200
    payload = response.json()
    report = FinalReport.model_validate(payload)
    assert report.projectId == project_id
    assert report.requirement is not None
    assert report.planObject is not None
    assert report.codeArtifact is None
    assert report.validationSummary == "Validation has not been run yet."
    assert report.optimizationSummary == "Optimization has not been run yet."
    assert report.metricsSummary == "Metrics have not been generated yet."


def test_report_includes_generated_code_and_validation(client: TestClient) -> None:
    project_id = _create_project(client)
    client.post(f"/api/projects/{project_id}/requirements", json=requirement_payload(project_id))
    client.post(f"/api/projects/{project_id}/plan")
    client.post(f"/api/projects/{project_id}/generate")
    client.post(f"/api/projects/{project_id}/validate")

    response = client.get(f"/api/projects/{project_id}/report")
    assert response.status_code == 200
    report = FinalReport.model_validate(response.json())
    assert report.codeArtifact is not None
    assert report.validation is not None
    assert report.validationSummary != "Validation has not been run yet."


def test_report_includes_optimization_and_metrics_after_pipeline(client: TestClient) -> None:
    project_id = _create_project(client)
    client.post(f"/api/projects/{project_id}/requirements", json=requirement_payload(project_id))
    client.post(f"/api/projects/{project_id}/plan")
    client.post(f"/api/projects/{project_id}/generate")
    client.post(f"/api/projects/{project_id}/validate")
    client.post(f"/api/projects/{project_id}/optimize")
    client.get(f"/api/projects/{project_id}/metrics")

    response = client.get(f"/api/projects/{project_id}/report")
    assert response.status_code == 200
    report = FinalReport.model_validate(response.json())
    assert report.optimization is not None
    assert report.metrics is not None
    assert report.optimizationSummary != "Optimization has not been run yet."
    assert report.metricsSummary != "Metrics have not been generated yet."


def test_report_json_export_returns_404_for_missing_project(client: TestClient) -> None:
    response = client.get("/api/projects/PRJ-9999/report/export/json")
    assert response.status_code == 404


def test_report_json_export_returns_downloadable_json(client: TestClient) -> None:
    project_id = _create_project(client)
    client.post(f"/api/projects/{project_id}/requirements", json=requirement_payload(project_id))
    client.post(f"/api/projects/{project_id}/plan")

    response = client.get(f"/api/projects/{project_id}/report/export/json")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert f'attachment; filename="plcforge_report_{project_id}.json"' == response.headers["content-disposition"]
    report = FinalReport.model_validate(response.json())
    assert report.projectId == project_id


def test_report_markdown_export_returns_downloadable_markdown(client: TestClient) -> None:
    project_id = _create_project(client)
    client.post(f"/api/projects/{project_id}/requirements", json=requirement_payload(project_id))
    client.post(f"/api/projects/{project_id}/plan")

    response = client.get(f"/api/projects/{project_id}/report/export/markdown")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert f'attachment; filename="plcforge_report_{project_id}.md"' == response.headers["content-disposition"]
    body = response.text
    assert "# PLCForge Final Report" in body
    assert "## Requirement" in body
    assert "## Plan Summary" in body
    assert "Control conveyor motor with E-stop and overload protection." in body


def test_report_markdown_export_shows_not_generated_yet_sections(client: TestClient) -> None:
    project_id = _create_project(client)
    client.post(f"/api/projects/{project_id}/requirements", json=requirement_payload(project_id))
    client.post(f"/api/projects/{project_id}/plan")

    response = client.get(f"/api/projects/{project_id}/report/export/markdown")
    assert response.status_code == 200
    body = response.text
    assert "## Debugging Summary" in body
    assert "## Repair Loop Summary" in body
    assert "## Generated Code" in body
    assert "Not generated yet" in body

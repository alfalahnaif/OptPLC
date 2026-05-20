import asyncio

from fastapi.testclient import TestClient

from app.database.database import AsyncSessionLocal
from app.database.models import ProjectModel, SessionModel


def create_project_payload() -> dict:
    return {
        "name": "Tank Level Control - T-204",
        "description": "Maintain tank level using inlet and outlet valves with high-high trip.",
        "domain": "Process Control",
        "targetLanguage": "Structured Text",
        "complexityTier": "medium",
    }


def requirement_payload(project_id: str, text: str | None = None) -> dict:
    return {
        "projectId": project_id,
        "text": text
        or (
            "Control a conveyor motor with Start_PB, Stop_PB, E_Stop, Overload, "
            "and Reset_PB. Faults must latch until reset."
        ),
        "safetyConstraints": [
            "Motor must not auto-restart after E-Stop",
            "Reset requires explicit operator action",
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


def _db_counts() -> tuple[int, int]:
    async def _run() -> tuple[int, int]:
        async with AsyncSessionLocal() as session:
            project_count = len((await session.execute(ProjectModel.__table__.select())).all())
            session_count = len((await session.execute(SessionModel.__table__.select())).all())
            return project_count, session_count

    return asyncio.run(_run())


def test_create_project_persists_in_sqlite(client: TestClient) -> None:
    response = client.post("/api/projects", json=create_project_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "draft"
    assert body["standard"] == "IEC 61131-3"
    projects, _ = _db_counts()
    assert projects == 1


def test_list_projects_reads_from_db(client: TestClient) -> None:
    project_id = _create_project(client)
    response = client.get("/api/projects")
    assert response.status_code == 200
    projects = response.json()
    assert len(projects) == 1
    assert projects[0]["id"] == project_id


def test_get_project_reads_from_db(client: TestClient) -> None:
    project_id = _create_project(client)
    response = client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200
    assert response.json()["id"] == project_id


def test_submit_requirement_persists(client: TestClient) -> None:
    project_id = _create_project(client)
    response = client.post(f"/api/projects/{project_id}/requirements", json=requirement_payload(project_id))
    assert response.status_code == 200
    event = response.json()
    assert event["projectId"] == project_id
    assert event["status"] == "completed"
    _, sessions = _db_counts()
    assert sessions == 1


def test_create_plan_persists_plan_object(client: TestClient) -> None:
    project_id = _create_project(client)
    client.post(f"/api/projects/{project_id}/requirements", json=requirement_payload(project_id))
    response = client.post(f"/api/projects/{project_id}/plan")
    assert response.status_code == 200
    plan = response.json()
    assert plan["projectId"] == project_id
    assert plan["agent"] == "PlanningAgent/rule_based.v1"


def test_generate_code_persists_artifact(client: TestClient) -> None:
    project_id = _create_project(client)
    client.post(f"/api/projects/{project_id}/requirements", json=requirement_payload(project_id))
    client.post(f"/api/projects/{project_id}/plan")
    response = client.post(f"/api/projects/{project_id}/generate")
    assert response.status_code == 200
    artifact = response.json()
    assert artifact["projectId"] == project_id
    assert artifact["language"] == "structured-text"


def test_validate_persists_validation_report(client: TestClient) -> None:
    project_id = _create_project(client)
    client.post(f"/api/projects/{project_id}/requirements", json=requirement_payload(project_id))
    client.post(f"/api/projects/{project_id}/plan")
    client.post(f"/api/projects/{project_id}/generate")
    response = client.post(f"/api/projects/{project_id}/validate")
    assert response.status_code == 200
    report = response.json()
    assert report["projectId"] == project_id
    assert report["validator"] == "static.v1"


def test_debug_persists_debugging_report(client: TestClient) -> None:
    project_id = _create_project(client)
    client.post(f"/api/projects/{project_id}/requirements", json=requirement_payload(project_id))
    client.post(f"/api/projects/{project_id}/plan")
    client.post(f"/api/projects/{project_id}/generate")
    client.post(f"/api/projects/{project_id}/validate")
    response = client.post(f"/api/projects/{project_id}/debug")
    assert response.status_code == 200
    assert response.json()["projectId"] == project_id


def test_repair_loop_persists_report(client: TestClient) -> None:
    project_id = _create_project(client)
    client.post(f"/api/projects/{project_id}/requirements", json=requirement_payload(project_id))
    client.post(f"/api/projects/{project_id}/plan")
    client.post(f"/api/projects/{project_id}/generate")
    response = client.post(f"/api/projects/{project_id}/repair-loop")
    assert response.status_code == 200
    report = response.json()
    assert report["projectId"] == project_id
    assert report["finalValidationReport"]["status"] in {"VERIFIED", "SYNTAX_ERROR", "FORMAL_VIOLATION"}


def test_optimize_persists_optimization_report(client: TestClient) -> None:
    project_id = _create_project(client)
    client.post(f"/api/projects/{project_id}/requirements", json=requirement_payload(project_id))
    client.post(f"/api/projects/{project_id}/plan")
    client.post(f"/api/projects/{project_id}/generate")
    client.post(f"/api/projects/{project_id}/validate")
    response = client.post(f"/api/projects/{project_id}/optimize")
    assert response.status_code == 200
    report = response.json()
    assert report["projectId"] == project_id
    assert report["optimizer"] == "static.v1"


def test_metrics_persists_metrics_report(client: TestClient) -> None:
    project_id = _create_project(client)
    client.post(f"/api/projects/{project_id}/requirements", json=requirement_payload(project_id))
    client.post(f"/api/projects/{project_id}/plan")
    client.post(f"/api/projects/{project_id}/generate")
    response = client.get(f"/api/projects/{project_id}/metrics")
    assert response.status_code == 200
    report = response.json()
    assert report["projectId"] == project_id
    assert "metricsDelta" in report


def test_data_survives_new_db_session(client: TestClient) -> None:
    project_id = _create_project(client)
    client.post(f"/api/projects/{project_id}/requirements", json=requirement_payload(project_id))

    async def _read() -> tuple[bool, bool]:
        async with AsyncSessionLocal() as session:
            project = await session.get(ProjectModel, project_id)
            rows = (await session.execute(SessionModel.__table__.select())).all()
            return project is not None, len(rows) == 1

    project_exists, session_exists = asyncio.run(_read())
    assert project_exists is True
    assert session_exists is True


def test_no_endpoint_returns_coroutine_object(client: TestClient) -> None:
    project_id = _create_project(client)
    responses = [
        client.get("/api/projects"),
        client.get(f"/api/projects/{project_id}"),
        client.post(f"/api/projects/{project_id}/requirements", json=requirement_payload(project_id)),
        client.post(f"/api/projects/{project_id}/plan"),
    ]
    for response in responses:
        assert response.status_code in {200, 201}
        assert "coroutine" not in response.text.lower()


def test_missing_prerequisites_return_400_guidance(client: TestClient) -> None:
    project_id = _create_project(client)
    r1 = client.post(f"/api/projects/{project_id}/generate")
    r2 = client.post(f"/api/projects/{project_id}/validate")
    r3 = client.post(f"/api/projects/{project_id}/debug")
    r4 = client.post(f"/api/projects/{project_id}/repair-loop")
    r5 = client.post(f"/api/projects/{project_id}/optimize")
    r6 = client.get(f"/api/projects/{project_id}/metrics")
    for response in [r1, r2, r3, r4, r5, r6]:
        assert response.status_code == 400
        assert "must be generated before" in response.json()["detail"] or "must be submitted before" in response.json()["detail"]

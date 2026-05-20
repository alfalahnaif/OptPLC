from fastapi.testclient import TestClient

from app.storage.memory import store


def requirement_payload(project_id: str) -> dict:
    return {
        "projectId": project_id,
        "text": (
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


def test_list_projects_includes_seed_project(client: TestClient) -> None:
    response = client.get("/api/projects")

    assert response.status_code == 200
    projects = response.json()
    assert len(projects) == 1
    assert projects[0]["id"] == "PRJ-0421"
    assert projects[0]["targetLanguage"] == "Structured Text"


def test_create_project(client: TestClient) -> None:
    response = client.post(
        "/api/projects",
        json={
            "name": "Tank Level Control - T-204",
            "description": "Maintain tank level using inlet and outlet valves with high-high trip.",
            "domain": "Process Control",
            "targetLanguage": "Structured Text",
            "complexityTier": "medium",
        },
    )

    assert response.status_code == 201
    project = response.json()
    assert project["id"] == "PRJ-0422"
    assert project["status"] == "draft"
    assert project["standard"] == "IEC 61131-3"


def test_get_project(client: TestClient) -> None:
    response = client.get("/api/projects/PRJ-0421")

    assert response.status_code == 200
    assert response.json()["name"] == "Motor Control - Conveyor M-12"


def test_get_project_not_found(client: TestClient) -> None:
    response = client.get("/api/projects/PRJ-9999")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_submit_requirements_returns_workflow_event(client: TestClient) -> None:
    response = client.post(
        "/api/projects/PRJ-0421/requirements",
        json=requirement_payload("PRJ-0421"),
    )

    assert response.status_code == 200
    event = response.json()
    assert event["projectId"] == "PRJ-0421"
    assert event["agent"] == "Planning Agent"
    assert event["status"] == "completed"
    assert "Plan Object" in event["outputSummary"]


def test_submit_requirements_requires_matching_project_id(client: TestClient) -> None:
    response = client.post(
        "/api/projects/PRJ-0421/requirements",
        json=requirement_payload("PRJ-9999"),
    )

    assert response.status_code == 400
    assert "match the route" in response.json()["detail"]


def test_submit_requirements_project_not_found(client: TestClient) -> None:
    response = client.post(
        "/api/projects/PRJ-9999/requirements",
        json=requirement_payload("PRJ-9999"),
    )

    assert response.status_code == 404


def test_create_plan_for_seed_project(client: TestClient) -> None:
    response = client.post("/api/projects/PRJ-0421/plan")

    assert response.status_code == 200
    plan = response.json()
    assert plan["projectId"] == "PRJ-0421"
    assert plan["agent"] == "PlanningAgent/rule_based.v1"
    assert len(plan["inputs"]) == 5
    assert len(plan["outputs"]) == 3
    assert {item["name"] for item in plan["inputs"]} >= {"Start_PB", "E_Stop", "Overload"}
    assert {item["name"] for item in plan["outputs"]} >= {"Motor_Run", "Fault_Lamp"}
    assert plan["scope"]["standard"] == "IEC 61131-3"
    assert plan["scope"]["language"] == "Structured Text"


def test_blank_requirement_submission_returns_400(client: TestClient) -> None:
    response = client.post(
        "/api/projects/PRJ-0421/requirements",
        json={
            **requirement_payload("PRJ-0421"),
            "text": "   ",
        },
    )

    assert response.status_code == 400
    assert "Requirement text must not be empty" in str(response.json()["detail"])


def test_traffic_light_plan_endpoint_returns_traffic_signals(client: TestClient) -> None:
    create_response = client.post(
        "/api/projects",
        json={
            "name": "Intersection 17 Traffic Signal",
            "description": "Traffic light sequence with pedestrian request.",
            "domain": "Traffic Control",
            "targetLanguage": "Structured Text",
            "complexityTier": "medium",
        },
    )
    project_id = create_response.json()["id"]
    client.post(
        f"/api/projects/{project_id}/requirements",
        json={
            **requirement_payload(project_id),
            "text": "Traffic light controller with vehicle detector and pedestrian request.",
        },
    )

    response = client.post(f"/api/projects/{project_id}/plan")

    assert response.status_code == 200
    plan = response.json()
    assert {item["name"] for item in plan["inputs"]} >= {"Vehicle_Detect", "Ped_Request", "Cycle_Timer"}
    assert {item["name"] for item in plan["outputs"]} >= {"Red_Light", "Amber_Light", "Green_Light", "Ped_Walk"}


def test_generated_plan_is_stored_in_memory(client: TestClient) -> None:
    response = client.post("/api/projects/PRJ-0421/plan")

    assert response.status_code == 200
    stored_plan = store.get_plan("PRJ-0421")
    assert stored_plan is not None
    assert stored_plan.projectId == "PRJ-0421"
    assert stored_plan.agent == "PlanningAgent/rule_based.v1"


def test_create_plan_requires_requirements(client: TestClient) -> None:
    create_response = client.post(
        "/api/projects",
        json={
            "name": "Intersection 17 Traffic Signal",
            "description": "Traffic light sequence with pedestrian request.",
            "domain": "Traffic Control",
            "targetLanguage": "Structured Text",
            "complexityTier": "medium",
        },
    )
    project_id = create_response.json()["id"]

    response = client.post(f"/api/projects/{project_id}/plan")

    assert response.status_code == 400
    assert "Requirements must be submitted" in response.json()["detail"]


def test_create_plan_project_not_found(client: TestClient) -> None:
    response = client.post("/api/projects/PRJ-9999/plan")

    assert response.status_code == 404


def test_generate_code_requires_plan_object(client: TestClient) -> None:
    response = client.post("/api/projects/PRJ-0421/generate")

    assert response.status_code == 400
    assert response.json()["detail"] == "PlanObject must be generated before code generation."


def test_generate_code_endpoint_returns_code_artifact(client: TestClient) -> None:
    plan_response = client.post("/api/projects/PRJ-0421/plan")
    assert plan_response.status_code == 200

    response = client.post("/api/projects/PRJ-0421/generate")

    assert response.status_code == 200
    artifact = response.json()
    assert artifact["projectId"] == "PRJ-0421"
    assert artifact["language"] == "structured-text"
    assert artifact["metadata"]["generator"] == "template_based.v1"
    assert "PROGRAM" in artifact["source"]
    assert "END_PROGRAM" in artifact["source"]


def test_generated_code_artifact_is_stored_in_memory(client: TestClient) -> None:
    client.post("/api/projects/PRJ-0421/plan")
    response = client.post("/api/projects/PRJ-0421/generate")

    assert response.status_code == 200
    stored_artifact = store.get_code_artifact("PRJ-0421")
    assert stored_artifact is not None
    assert stored_artifact.projectId == "PRJ-0421"
    assert stored_artifact.metadata.generator == "template_based.v1"


def test_validate_code_requires_code_artifact(client: TestClient) -> None:
    client.post("/api/projects/PRJ-0421/plan")

    response = client.post("/api/projects/PRJ-0421/validate")

    assert response.status_code == 400
    assert response.json()["detail"] == "CodeArtifact must be generated before validation."


def test_validate_code_requires_plan_object(client: TestClient) -> None:
    response = client.post("/api/projects/PRJ-0421/validate")

    assert response.status_code == 400
    assert response.json()["detail"] == "PlanObject must be generated before validation."


def test_validate_code_endpoint_returns_validation_report(client: TestClient) -> None:
    client.post("/api/projects/PRJ-0421/plan")
    client.post("/api/projects/PRJ-0421/generate")

    response = client.post("/api/projects/PRJ-0421/validate")

    assert response.status_code == 200
    report = response.json()
    assert report["projectId"] == "PRJ-0421"
    assert report["status"] == "VERIFIED"
    assert report["syntaxPassed"] is True
    assert report["formalPassed"] is True
    assert report["validator"] == "static.v1"
    assert report["syntaxErrors"] == []
    assert len(report["safetyResults"]) >= 1


def test_validation_report_is_stored_in_memory(client: TestClient) -> None:
    client.post("/api/projects/PRJ-0421/plan")
    client.post("/api/projects/PRJ-0421/generate")
    response = client.post("/api/projects/PRJ-0421/validate")

    assert response.status_code == 200
    stored_report = store.get_validation_report("PRJ-0421")
    assert stored_report is not None
    assert stored_report.projectId == "PRJ-0421"
    assert stored_report.status == "VERIFIED"


def test_debug_code_requires_validation_report(client: TestClient) -> None:
    client.post("/api/projects/PRJ-0421/plan")
    client.post("/api/projects/PRJ-0421/generate")

    response = client.post("/api/projects/PRJ-0421/debug")

    assert response.status_code == 400
    assert response.json()["detail"] == "ValidationReport must be generated before debugging."


def test_debug_code_requires_code_artifact(client: TestClient) -> None:
    client.post("/api/projects/PRJ-0421/plan")

    response = client.post("/api/projects/PRJ-0421/debug")

    assert response.status_code == 400
    assert response.json()["detail"] == "CodeArtifact must be generated before debugging."


def test_debug_code_requires_plan_object(client: TestClient) -> None:
    response = client.post("/api/projects/PRJ-0421/debug")

    assert response.status_code == 400
    assert response.json()["detail"] == "PlanObject must be generated before debugging."


def test_debug_code_endpoint_returns_debugging_report(client: TestClient) -> None:
    client.post("/api/projects/PRJ-0421/plan")
    client.post("/api/projects/PRJ-0421/generate")
    client.post("/api/projects/PRJ-0421/validate")

    response = client.post("/api/projects/PRJ-0421/debug")

    assert response.status_code == 200
    report = response.json()
    assert report["projectId"] == "PRJ-0421"
    assert report["status"] == "NOT_REQUIRED"
    assert report["sourceValidationStatus"] == "VERIFIED"
    assert report["debugger"] == "rule_based.v1"


def test_debugging_report_is_stored_in_memory(client: TestClient) -> None:
    client.post("/api/projects/PRJ-0421/plan")
    client.post("/api/projects/PRJ-0421/generate")
    client.post("/api/projects/PRJ-0421/validate")
    response = client.post("/api/projects/PRJ-0421/debug")

    assert response.status_code == 200
    stored_report = store.get_debugging_report("PRJ-0421")
    assert stored_report is not None
    assert stored_report.projectId == "PRJ-0421"
    assert stored_report.debugger == "rule_based.v1"


def test_repair_loop_requires_code_artifact(client: TestClient) -> None:
    client.post("/api/projects/PRJ-0421/plan")

    response = client.post("/api/projects/PRJ-0421/repair-loop")

    assert response.status_code == 400
    assert response.json()["detail"] == "CodeArtifact must be generated before running repair loop."


def test_repair_loop_requires_plan_object(client: TestClient) -> None:
    response = client.post("/api/projects/PRJ-0421/repair-loop")

    assert response.status_code == 400
    assert response.json()["detail"] == "PlanObject must be generated before running repair loop."


def test_repair_loop_endpoint_returns_report(client: TestClient) -> None:
    client.post("/api/projects/PRJ-0421/plan")
    client.post("/api/projects/PRJ-0421/generate")

    response = client.post("/api/projects/PRJ-0421/repair-loop")

    assert response.status_code == 200
    report = response.json()
    assert report["projectId"] == "PRJ-0421"
    assert report["finalStatus"] == "VERIFIED"
    assert report["iterations"] == 1
    assert report["finalCodeArtifact"]["language"] == "structured-text"
    assert report["finalValidationReport"]["status"] == "VERIFIED"

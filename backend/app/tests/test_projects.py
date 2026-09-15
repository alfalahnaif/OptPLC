import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database.database import AsyncSessionLocal
from app.database.models import ProjectModel, SessionModel
from app.tests.support.scan_sim import ScanSim


def create_project_payload() -> dict:
    return {
        "name": "Conveyor Motor Control - M-204",
        "description": "Control a motor with start, stop, emergency stop, overload, and reset handling.",
        "domain": "Motor Control",
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
        "confirmedOutputs": [],
    }


def _create_project(client: TestClient) -> str:
    response = client.post("/api/projects", json=create_project_payload())
    assert response.status_code == 201
    return response.json()["id"]


def _create_sequential_batch_project(client: TestClient) -> str:
    payload = {
        "name": "Batch Reactor - B-22",
        "description": "Sequential batch process with fill, mix and drain phases.",
        "domain": "Sequential Batch",
        "targetLanguage": "Structured Text",
        "complexityTier": "complex",
    }
    created = client.post("/api/projects", json=payload)
    assert created.status_code == 201
    return created.json()["id"]


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


def test_create_and_get_project_persists_sequential_batch_domain(client: TestClient) -> None:
    payload = create_project_payload()
    payload["name"] = "Batch Reactor - B-11"
    payload["description"] = "Sequential batch process with fill, heat, mix and drain."
    payload["domain"] = "Sequential Batch"
    payload["complexityTier"] = "complex"

    created = client.post("/api/projects", json=payload)
    assert created.status_code == 201
    project_id = created.json()["id"]
    assert created.json()["domain"] == "Sequential Batch"
    assert created.json()["targetLanguage"] == "Structured Text"

    fetched = client.get(f"/api/projects/{project_id}")
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["id"] == project_id
    assert body["name"] == "Batch Reactor - B-11"
    assert body["description"] == "Sequential batch process with fill, heat, mix and drain."
    assert body["domain"] == "Sequential Batch"


def test_submit_requirement_persists(client: TestClient) -> None:
    project_id = _create_project(client)
    response = client.post(f"/api/projects/{project_id}/requirements", json=requirement_payload(project_id))
    assert response.status_code == 200
    event = response.json()
    assert event["projectId"] == project_id
    assert event["status"] == "completed"
    _, sessions = _db_counts()
    assert sessions == 1


def test_submit_requirement_persists_constraints_and_performance_targets(client: TestClient) -> None:
    project_id = _create_project(client)
    payload = requirement_payload(project_id)
    payload["safetyConstraints"] = ["User constraint A", "User constraint B"]
    payload["performanceTargets"] = {
        "maxScanTimeMs": 7,
        "maxCyclomaticComplexity": 11,
        "minMaintainabilityIndex": 72,
        "maxIterations": 6,
    }
    response = client.post(f"/api/projects/{project_id}/requirements", json=payload)
    assert response.status_code == 200

    async def _read() -> tuple[list[str], dict]:
        async with AsyncSessionLocal() as session:
            model = (await session.execute(select(SessionModel).where(SessionModel.project_id == project_id))).scalar_one()
            return list(model.safety_constraints), dict(model.requirement_input["performanceTargets"])

    constraints, performance_targets = asyncio.run(_read())
    assert constraints == ["User constraint A", "User constraint B"]
    assert performance_targets == payload["performanceTargets"]


def test_submit_requirement_accepts_snake_case_contract_fields(client: TestClient) -> None:
    project_id = _create_project(client)
    payload = {
        "projectId": project_id,
        "text": "Motor control with emergency stop and overload.",
        "safety_constraints": ["Snake case safety constraint"],
        "performance_targets": {
            "maxScanTimeMs": 6,
            "maxCyclomaticComplexity": 9,
            "minMaintainabilityIndex": 74,
            "maxIterations": 5,
        },
        "confirmed_outputs": ["Fault_Lamp"],
        "complexity_tier": "medium",
    }
    response = client.post(f"/api/projects/{project_id}/requirements", json=payload)
    assert response.status_code == 200

    plan = client.post(f"/api/projects/{project_id}/plan")
    assert plan.status_code == 200
    assert "Snake case safety constraint" in plan.json()["safetyConstraints"]


def test_get_requirements_returns_404_for_missing_project(client: TestClient) -> None:
    response = client.get("/api/projects/PRJ-9999/requirements")
    assert response.status_code == 404
    assert "was not found" in response.json()["detail"]


def test_get_requirements_returns_404_when_no_requirement_submitted(client: TestClient) -> None:
    project_id = _create_project(client)
    response = client.get(f"/api/projects/{project_id}/requirements")
    assert response.status_code == 404
    assert "Requirements for project" in response.json()["detail"]


def test_get_requirements_returns_submitted_payload(client: TestClient) -> None:
    project_id = _create_project(client)
    payload = requirement_payload(project_id)
    payload["text"] = "Persist this requirement text."
    payload["safetyConstraints"] = ["Constraint A", "Constraint B"]
    payload["performanceTargets"] = {
        "maxScanTimeMs": 9,
        "maxCyclomaticComplexity": 12,
        "minMaintainabilityIndex": 70,
        "maxIterations": 6,
    }

    submit_response = client.post(f"/api/projects/{project_id}/requirements", json=payload)
    assert submit_response.status_code == 200

    response = client.get(f"/api/projects/{project_id}/requirements")
    assert response.status_code == 200
    body = response.json()
    assert body["projectId"] == project_id
    assert body["text"] == "Persist this requirement text."
    assert body["safetyConstraints"] == ["Constraint A", "Constraint B"]
    assert body["performanceTargets"] == payload["performanceTargets"]
    assert body["domain"] == "Motor Control"
    assert body["complexityTier"] == "medium"
    assert body["submittedAt"]
    assert body["updatedAt"]


def test_create_plan_persists_plan_object(client: TestClient) -> None:
    project_id = _create_project(client)
    client.post(f"/api/projects/{project_id}/requirements", json=requirement_payload(project_id))
    response = client.post(f"/api/projects/{project_id}/plan")
    assert response.status_code == 200
    plan = response.json()
    assert plan["projectId"] == project_id
    assert plan["agent"] == "PlanningAgent/rule_based.v1"


def test_create_plan_uses_stored_requirement_constraints(client: TestClient) -> None:
    project_id = _create_project(client)
    payload = requirement_payload(
        project_id,
        text="Control motor start/stop with emergency stop and overload; include fault lamp only.",
    )
    payload["safetyConstraints"] = ["User constraint A", "User constraint B"]
    client.post(f"/api/projects/{project_id}/requirements", json=payload)
    response = client.post(f"/api/projects/{project_id}/plan")
    assert response.status_code == 200
    plan = response.json()
    assert "User constraint A" in plan["safetyConstraints"]
    assert "User constraint B" in plan["safetyConstraints"]


def test_create_plan_preserves_exact_constraint_count(client: TestClient) -> None:
    project_id = _create_project(client)
    payload = requirement_payload(
        project_id,
        text="Motor start/stop with emergency stop and overload.",
    )
    payload["safetyConstraints"] = ["C1", "C2", "C3", "C4"]
    client.post(f"/api/projects/{project_id}/requirements", json=payload)
    response = client.post(f"/api/projects/{project_id}/plan")
    assert response.status_code == 200
    assert response.json()["safetyConstraints"] == ["C1", "C2", "C3", "C4"]


def test_create_plan_preserves_exact_constraint_count_for_five_constraints(client: TestClient) -> None:
    project_id = _create_project(client)
    payload = requirement_payload(project_id, text="Motor control with emergency stop and overload.")
    payload["safetyConstraints"] = ["SC1", "SC2", "SC3", "SC4", "SC5"]
    client.post(f"/api/projects/{project_id}/requirements", json=payload)
    response = client.post(f"/api/projects/{project_id}/plan")
    assert response.status_code == 200
    assert response.json()["safetyConstraints"] == ["SC1", "SC2", "SC3", "SC4", "SC5"]


def test_create_plan_preserves_exact_constraint_count_for_three_constraints(client: TestClient) -> None:
    project_id = _create_project(client)
    payload = requirement_payload(project_id, text="Motor control with emergency stop and overload.")
    payload["safetyConstraints"] = ["SC1", "SC2", "SC3"]
    client.post(f"/api/projects/{project_id}/requirements", json=payload)
    response = client.post(f"/api/projects/{project_id}/plan")
    assert response.status_code == 200
    assert response.json()["safetyConstraints"] == ["SC1", "SC2", "SC3"]


def test_plan_outputs_only_confirmed_outputs(client: TestClient) -> None:
    project_id = _create_project(client)
    payload = requirement_payload(
        project_id,
        text="Control motor start/stop with emergency stop and overload protection.",
    )
    payload["confirmedOutputs"] = []
    client.post(f"/api/projects/{project_id}/requirements", json=payload)
    response = client.post(f"/api/projects/{project_id}/plan")
    assert response.status_code == 200
    output_names = {item["name"] for item in response.json()["outputs"]}
    assert output_names == {"Motor_Run"}


def test_motor_requirement_with_fault_lamp_text_includes_fault_lamp(client: TestClient) -> None:
    project_id = _create_project(client)
    payload = requirement_payload(
        project_id,
        text="Control motor start/stop with emergency stop and fault lamp indication.",
    )
    client.post(f"/api/projects/{project_id}/requirements", json=payload)
    response = client.post(f"/api/projects/{project_id}/plan")
    assert response.status_code == 200
    output_names = {item["name"] for item in response.json()["outputs"]}
    assert "Fault_Lamp" in output_names


def test_motor_requirement_without_reset_does_not_include_reset_input(client: TestClient) -> None:
    project_id = _create_project(client)
    payload = requirement_payload(
        project_id,
        text="Control motor start/stop with emergency stop and overload protection.",
    )
    payload["safetyConstraints"] = ["Emergency stop must trip output."]
    client.post(f"/api/projects/{project_id}/requirements", json=payload)
    response = client.post(f"/api/projects/{project_id}/plan")
    assert response.status_code == 200
    input_names = {item["name"] for item in response.json()["inputs"]}
    assert "Reset_PB" not in input_names


def test_motor_requirement_with_reset_includes_reset_input(client: TestClient) -> None:
    project_id = _create_project(client)
    payload = requirement_payload(
        project_id,
        text="Control motor start/stop with emergency stop, overload, and reset pushbutton.",
    )
    client.post(f"/api/projects/{project_id}/requirements", json=payload)
    response = client.post(f"/api/projects/{project_id}/plan")
    assert response.status_code == 200
    input_names = {item["name"] for item in response.json()["inputs"]}
    assert "Reset_PB" in input_names


def test_motor_requirement_canonicalizes_emergency_stop_name(client: TestClient) -> None:
    project_id = _create_project(client)
    payload = requirement_payload(
        project_id,
        text="Control motor start/stop with E-stop and overload protection.",
    )
    payload["safetyConstraints"] = ["Motor must not auto-restart after E-Stop"]
    client.post(f"/api/projects/{project_id}/requirements", json=payload)
    response = client.post(f"/api/projects/{project_id}/plan")
    assert response.status_code == 200
    input_names = {item["name"] for item in response.json()["inputs"]}
    assert "Emergency_Stop" in input_names
    assert "E_Stop" not in input_names
    # C-08 (P1-08): the signal name is canonical, but the user's constraint text is kept as written.
    assert response.json()["safetyConstraints"] == ["Motor must not auto-restart after E-Stop"]


def test_get_plan_returns_same_persisted_plan_object(client: TestClient) -> None:
    project_id = _create_project(client)
    payload = requirement_payload(project_id, text="Control motor start/stop with emergency stop and overload.")
    client.post(f"/api/projects/{project_id}/requirements", json=payload)
    created = client.post(f"/api/projects/{project_id}/plan")
    assert created.status_code == 200
    fetched = client.get(f"/api/projects/{project_id}/plan")
    assert fetched.status_code == 200
    assert fetched.json() == created.json()


def test_plan_object_changes_when_requirement_changes(client: TestClient) -> None:
    project_id = _create_project(client)
    first_payload = requirement_payload(project_id, text="Control motor start/stop with emergency stop and overload.")
    first_payload["safetyConstraints"] = ["Constraint alpha"]
    client.post(f"/api/projects/{project_id}/requirements", json=first_payload)
    first_plan = client.post(f"/api/projects/{project_id}/plan")
    assert first_plan.status_code == 200

    second_payload = requirement_payload(project_id, text="Control motor start/stop with emergency stop, overload, and reset pushbutton.")
    second_payload["safetyConstraints"] = ["Constraint beta"]
    client.post(f"/api/projects/{project_id}/requirements", json=second_payload)
    second_plan = client.post(f"/api/projects/{project_id}/plan")
    assert second_plan.status_code == 200

    assert first_plan.json()["safetyConstraints"] != second_plan.json()["safetyConstraints"]
    assert first_plan.json()["inputs"] != second_plan.json()["inputs"]


def test_plan_includes_accepted_suggested_outputs(client: TestClient) -> None:
    project_id = _create_project(client)
    payload = requirement_payload(
        project_id,
        text="Control motor start/stop with emergency stop and overload protection.",
    )
    payload["confirmedOutputs"] = ["Fault_Lamp"]
    client.post(f"/api/projects/{project_id}/requirements", json=payload)
    response = client.post(f"/api/projects/{project_id}/plan")
    assert response.status_code == 200
    output_names = {item["name"] for item in response.json()["outputs"]}
    assert "Fault_Lamp" in output_names
    assert "Ready_Lamp" not in output_names


def test_confirmed_outputs_are_persisted_in_requirement_input(client: TestClient) -> None:
    project_id = _create_project(client)
    payload = requirement_payload(project_id)
    payload["confirmedOutputs"] = ["Fault_Lamp", "Ready_Lamp"]
    response = client.post(f"/api/projects/{project_id}/requirements", json=payload)
    assert response.status_code == 200

    async def _read_confirmed_outputs() -> list[str]:
        async with AsyncSessionLocal() as session:
            model = (await session.execute(select(SessionModel).where(SessionModel.project_id == project_id))).scalar_one()
            return list(model.requirement_input["confirmedOutputs"])

    assert asyncio.run(_read_confirmed_outputs()) == ["Fault_Lamp", "Ready_Lamp"]


def test_unaccepted_suggested_outputs_are_not_included_for_sequential_batch(client: TestClient) -> None:
    project_id = _create_sequential_batch_project(client)
    payload = requirement_payload(
        project_id,
        text="Sequential batch process with emergency stop, abort, and reset handling.",
    )
    payload["confirmedOutputs"] = []
    submit = client.post(f"/api/projects/{project_id}/requirements", json=payload)
    assert submit.status_code == 200

    response = client.post(f"/api/projects/{project_id}/plan")
    assert response.status_code == 200
    output_names = {item["name"] for item in response.json()["outputs"]}
    assert "Fill_Valve" not in output_names
    assert "Mixer_Motor" not in output_names
    assert "Drain_Valve" not in output_names
    assert "Batch_Complete" not in output_names


def test_sequential_batch_plan_uses_batch_signals_and_not_motor_outputs(client: TestClient) -> None:
    project_id = _create_sequential_batch_project(client)

    req = requirement_payload(
        project_id,
        text=(
            "Run a sequential batch with fill, mix and drain. "
            "Use high and low level switches, a mix done input, emergency stop, abort, and reset. "
            "Set batch complete at cycle end."
        ),
    )
    submit = client.post(f"/api/projects/{project_id}/requirements", json=req)
    assert submit.status_code == 200

    response = client.post(f"/api/projects/{project_id}/plan")
    assert response.status_code == 200
    plan = response.json()
    input_names = {item["name"] for item in plan["inputs"]}
    output_names = {item["name"] for item in plan["outputs"]}

    assert output_names >= {"Fill_Valve", "Mixer_Motor", "Drain_Valve", "Batch_Complete"}
    assert "Motor_Run" not in output_names
    assert input_names >= {"High_Level", "Low_Level", "Mix_Timer_Done"}


def test_motor_control_plan_still_contains_motor_run_output(client: TestClient) -> None:
    payload = {
        "name": "Motor Conveyor - M-12",
        "description": "Motor start stop control with overload and emergency stop.",
        "domain": "Motor Control",
        "targetLanguage": "Structured Text",
        "complexityTier": "medium",
    }
    created = client.post("/api/projects", json=payload)
    assert created.status_code == 201
    project_id = created.json()["id"]

    req = requirement_payload(
        project_id,
        text="Control motor start/stop with emergency stop and overload protection.",
    )
    submit = client.post(f"/api/projects/{project_id}/requirements", json=req)
    assert submit.status_code == 200

    response = client.post(f"/api/projects/{project_id}/plan")
    assert response.status_code == 200
    output_names = {item["name"] for item in response.json()["outputs"]}
    assert "Motor_Run" in output_names


def test_sequential_batch_confirmed_outputs_are_included_in_plan(client: TestClient) -> None:
    project_id = _create_sequential_batch_project(client)
    req = requirement_payload(
        project_id,
        text="Sequential batch process with emergency stop and reset.",
    )
    req["confirmedOutputs"] = ["Fill_Valve", "Mixer_Motor", "Drain_Valve", "Batch_Complete"]
    submit = client.post(f"/api/projects/{project_id}/requirements", json=req)
    assert submit.status_code == 200

    response = client.post(f"/api/projects/{project_id}/plan")
    assert response.status_code == 200
    output_names = {item["name"] for item in response.json()["outputs"]}
    assert output_names >= {"Fill_Valve", "Mixer_Motor", "Drain_Valve", "Batch_Complete"}
    assert "Motor_Run" not in output_names


def test_sequential_batch_infers_explicitly_mentioned_outputs_without_confirmed_outputs(client: TestClient) -> None:
    project_id = _create_sequential_batch_project(client)
    req = requirement_payload(
        project_id,
        text="Sequential batch process controlling Fill_Valve, Mixer_Motor, Drain_Valve, and Batch_Complete.",
    )
    req["confirmedOutputs"] = []
    submit = client.post(f"/api/projects/{project_id}/requirements", json=req)
    assert submit.status_code == 200

    response = client.post(f"/api/projects/{project_id}/plan")
    assert response.status_code == 200
    output_names = {item["name"] for item in response.json()["outputs"]}
    assert output_names >= {"Fill_Valve", "Mixer_Motor", "Drain_Valve", "Batch_Complete"}


def test_sequential_batch_does_not_include_motor_run_unless_explicitly_requested(client: TestClient) -> None:
    project_id = _create_sequential_batch_project(client)
    req = requirement_payload(
        project_id,
        text="Sequential batch process with Fill_Valve, Mixer_Motor, Drain_Valve, and Batch_Complete.",
    )
    submit = client.post(f"/api/projects/{project_id}/requirements", json=req)
    assert submit.status_code == 200

    response = client.post(f"/api/projects/{project_id}/plan")
    assert response.status_code == 200
    output_names = {item["name"] for item in response.json()["outputs"]}
    assert "Motor_Run" not in output_names


def test_sequential_batch_includes_motor_run_when_explicitly_requested(client: TestClient) -> None:
    project_id = _create_sequential_batch_project(client)
    req = requirement_payload(
        project_id,
        text="Sequential batch process with Motor_Run, Fill_Valve, Mixer_Motor, Drain_Valve, and Batch_Complete.",
    )
    submit = client.post(f"/api/projects/{project_id}/requirements", json=req)
    assert submit.status_code == 200

    response = client.post(f"/api/projects/{project_id}/plan")
    assert response.status_code == 200
    output_names = {item["name"] for item in response.json()["outputs"]}
    assert "Motor_Run" in output_names


def test_submit_requirements_persists_performance_targets_exactly(client: TestClient) -> None:
    project_id = _create_project(client)
    payload = requirement_payload(project_id)
    payload["performanceTargets"] = {
        "maxScanTimeMs": 13,
        "maxCyclomaticComplexity": 17,
        "minMaintainabilityIndex": 66,
        "maxIterations": 9,
    }
    response = client.post(f"/api/projects/{project_id}/requirements", json=payload)
    assert response.status_code == 200

    async def _read_perf() -> dict:
        async with AsyncSessionLocal() as session:
            model = (await session.execute(select(SessionModel).where(SessionModel.project_id == project_id))).scalar_one()
            return dict(model.requirement_input["performanceTargets"])

    assert asyncio.run(_read_perf()) == payload["performanceTargets"]


def test_create_plan_uses_persisted_requirement_payload_not_defaults(client: TestClient) -> None:
    project_id = _create_project(client)
    first = requirement_payload(project_id, text="Motor start stop with emergency stop.")
    first["safetyConstraints"] = ["First constraint"]
    client.post(f"/api/projects/{project_id}/requirements", json=first)
    first_plan = client.post(f"/api/projects/{project_id}/plan")
    assert first_plan.status_code == 200

    second = requirement_payload(project_id, text="Motor start stop with emergency stop and overload.")
    second["safetyConstraints"] = ["Second constraint", "Third constraint"]
    second["confirmedOutputs"] = ["Fault_Lamp"]
    client.post(f"/api/projects/{project_id}/requirements", json=second)
    second_plan = client.post(f"/api/projects/{project_id}/plan")
    assert second_plan.status_code == 200
    second_body = second_plan.json()
    assert second_body["safetyConstraints"] == ["Second constraint", "Third constraint"]
    assert "Fault_Lamp" in {item["name"] for item in second_body["outputs"]}


def test_different_project_domains_generate_different_code(client: TestClient) -> None:
    batch_project = client.post(
        "/api/projects",
        json={
            "name": "Batch Reactor - B-31",
            "description": "Sequential batch process with fill, mix and drain.",
            "domain": "Sequential Batch",
            "targetLanguage": "Structured Text",
            "complexityTier": "complex",
        },
    )
    assert batch_project.status_code == 201
    batch_id = batch_project.json()["id"]
    client.post(
        f"/api/projects/{batch_id}/requirements",
        json=requirement_payload(
            batch_id,
            text=(
                "Run a sequential batch with fill, mix and drain. "
                "Use high and low level switches, emergency stop, abort, and reset."
            ),
        ),
    )
    client.post(f"/api/projects/{batch_id}/plan")
    batch_generated = client.post(f"/api/projects/{batch_id}/generate")
    assert batch_generated.status_code == 200
    batch_source = batch_generated.json()["source"]

    motor_project = client.post(
        "/api/projects",
        json={
            "name": "Conveyor Motor - M-31",
            "description": "Motor start stop control with overload and emergency stop.",
            "domain": "Motor Control",
            "targetLanguage": "Structured Text",
            "complexityTier": "medium",
        },
    )
    assert motor_project.status_code == 201
    motor_id = motor_project.json()["id"]
    client.post(
        f"/api/projects/{motor_id}/requirements",
        json=requirement_payload(
            motor_id,
            text="Control motor start/stop with emergency stop and overload protection.",
        ),
    )
    client.post(f"/api/projects/{motor_id}/plan")
    motor_generated = client.post(f"/api/projects/{motor_id}/generate")
    assert motor_generated.status_code == 200
    motor_source = motor_generated.json()["source"]

    assert "CASE Step_State OF" in batch_source
    assert "Motor_Run := Run_Cmd AND Safety_OK AND NOT Fault_State;" in motor_source
    assert batch_source != motor_source


def test_generate_code_persists_artifact(client: TestClient) -> None:
    project_id = _create_project(client)
    client.post(f"/api/projects/{project_id}/requirements", json=requirement_payload(project_id))
    client.post(f"/api/projects/{project_id}/plan")
    response = client.post(f"/api/projects/{project_id}/generate")
    assert response.status_code == 200
    artifact = response.json()
    assert artifact["projectId"] == project_id
    assert artifact["language"] == "structured-text"
    assert "Emergency_Stop" in artifact["source"]
    assert "E_Stop" not in artifact["source"]
    # Behavior, not wording (P1-22): Stop_PB is normally closed, so FALSE stops and blocks a start.
    sim = ScanSim(artifact["source"])
    inputs = {name: False for name in ("Start_PB", "Overload", "Reset_PB") if name.upper() in sim.inputs}
    healthy = {**inputs, "Stop_PB": True, "Emergency_Stop": True}
    assert sim.scan(**{**healthy, "Start_PB": True})["Motor_Run"] is True
    assert sim.scan(**{**healthy, "Stop_PB": False})["Motor_Run"] is False
    assert sim.scan(**{**healthy, "Start_PB": True, "Stop_PB": False})["Motor_Run"] is False


def test_artifact_get_endpoints_return_persisted_values(client: TestClient) -> None:
    project_id = _create_project(client)
    client.post(f"/api/projects/{project_id}/requirements", json=requirement_payload(project_id))
    client.post(f"/api/projects/{project_id}/plan")
    client.post(f"/api/projects/{project_id}/generate")
    client.post(f"/api/projects/{project_id}/validate")
    client.post(f"/api/projects/{project_id}/debug")
    client.post(f"/api/projects/{project_id}/optimize")

    plan_response = client.get(f"/api/projects/{project_id}/plan")
    code_response = client.get(f"/api/projects/{project_id}/code")
    validation_response = client.get(f"/api/projects/{project_id}/validation")
    debug_response = client.get(f"/api/projects/{project_id}/debug")
    optimization_response = client.get(f"/api/projects/{project_id}/optimization")

    assert plan_response.status_code == 200
    assert code_response.status_code == 200
    assert validation_response.status_code == 200
    assert debug_response.status_code == 200
    assert optimization_response.status_code == 200
    assert plan_response.json()["projectId"] == project_id
    assert code_response.json()["projectId"] == project_id
    assert validation_response.json()["projectId"] == project_id
    assert debug_response.json()["projectId"] == project_id
    assert optimization_response.json()["projectId"] == project_id


def test_artifact_get_endpoints_return_404_when_missing(client: TestClient) -> None:
    project_id = _create_project(client)
    assert client.get(f"/api/projects/{project_id}/plan").status_code == 404
    assert client.get(f"/api/projects/{project_id}/code").status_code == 404
    assert client.get(f"/api/projects/{project_id}/validation").status_code == 404
    assert client.get(f"/api/projects/{project_id}/debug").status_code == 404
    assert client.get(f"/api/projects/{project_id}/optimization").status_code == 404


def test_validate_persists_validation_report(client: TestClient) -> None:
    project_id = _create_project(client)
    client.post(f"/api/projects/{project_id}/requirements", json=requirement_payload(project_id))
    client.post(f"/api/projects/{project_id}/plan")
    client.post(f"/api/projects/{project_id}/generate")
    response = client.post(f"/api/projects/{project_id}/validate")
    assert response.status_code == 200
    report = response.json()
    assert report["projectId"] == project_id
    assert report["validator"] == "parser.v1"
    assert "status" in report
    assert "syntaxErrors" in report
    assert "safetyResults" in report
    assert "checkedAt" in report


def test_get_validation_returns_same_persisted_report(client: TestClient) -> None:
    project_id = _create_project(client)
    client.post(f"/api/projects/{project_id}/requirements", json=requirement_payload(project_id))
    client.post(f"/api/projects/{project_id}/plan")
    client.post(f"/api/projects/{project_id}/generate")
    created = client.post(f"/api/projects/{project_id}/validate")
    assert created.status_code == 200

    fetched = client.get(f"/api/projects/{project_id}/validation")
    assert fetched.status_code == 200
    assert fetched.json() == created.json()


def test_validate_returns_400_when_code_artifact_missing(client: TestClient) -> None:
    project_id = _create_project(client)
    client.post(f"/api/projects/{project_id}/requirements", json=requirement_payload(project_id))
    client.post(f"/api/projects/{project_id}/plan")

    response = client.post(f"/api/projects/{project_id}/validate")
    assert response.status_code == 400
    assert response.json()["detail"] == "CodeArtifact must be generated before validation."


def test_debug_persists_debugging_report(client: TestClient) -> None:
    project_id = _create_project(client)
    client.post(f"/api/projects/{project_id}/requirements", json=requirement_payload(project_id))
    client.post(f"/api/projects/{project_id}/plan")
    client.post(f"/api/projects/{project_id}/generate")
    client.post(f"/api/projects/{project_id}/validate")
    response = client.post(f"/api/projects/{project_id}/debug")
    assert response.status_code == 200
    assert response.json()["projectId"] == project_id


def test_debug_after_verified_validation_returns_not_required(client: TestClient) -> None:
    project_id = _create_project(client)
    client.post(f"/api/projects/{project_id}/requirements", json=requirement_payload(project_id))
    client.post(f"/api/projects/{project_id}/plan")
    client.post(f"/api/projects/{project_id}/generate")
    client.post(f"/api/projects/{project_id}/validate")

    response = client.post(f"/api/projects/{project_id}/debug")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "NOT_REQUIRED"
    assert body["sourceValidationStatus"] == "CHECKS_PASSED"


def test_debug_after_failed_validation_returns_patch_advice(client: TestClient) -> None:
    project_id = _create_project(client)
    client.post(f"/api/projects/{project_id}/requirements", json=requirement_payload(project_id))
    client.post(f"/api/projects/{project_id}/plan")
    client.post(f"/api/projects/{project_id}/generate")

    async def _corrupt_artifact() -> None:
        async with AsyncSessionLocal() as session:
            model = (await session.execute(select(SessionModel).where(SessionModel.project_id == project_id))).scalar_one()
            artifact = dict(model.code_artifact)
            artifact["source"] = artifact["source"].replace("END_PROGRAM", "")
            history = list(model.code_artifact_history or [])
            if history:
                history[-1] = artifact
            await session.execute(
                SessionModel.__table__.update()
                .where(SessionModel.id == model.id)
                .values(code_artifact=artifact, code_artifact_history=history)
            )
            await session.commit()

    asyncio.run(_corrupt_artifact())
    validate_response = client.post(f"/api/projects/{project_id}/validate")
    assert validate_response.status_code == 200
    assert validate_response.json()["status"] in {"SYNTAX_ERROR", "FORMAL_VIOLATION"}

    debug_response = client.post(f"/api/projects/{project_id}/debug")
    assert debug_response.status_code == 200
    assert debug_response.json()["status"] == "PATCH_ADVICE_GENERATED"


def test_repair_loop_persists_report(client: TestClient) -> None:
    project_id = _create_project(client)
    client.post(f"/api/projects/{project_id}/requirements", json=requirement_payload(project_id))
    client.post(f"/api/projects/{project_id}/plan")
    client.post(f"/api/projects/{project_id}/generate")
    response = client.post(f"/api/projects/{project_id}/repair-loop")
    assert response.status_code == 200
    report = response.json()
    assert report["projectId"] == project_id
    assert report["finalValidationReport"]["status"] in {"CHECKS_PASSED", "SYNTAX_ERROR", "FORMAL_VIOLATION"}


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


def test_get_optimization_returns_same_persisted_report(client: TestClient) -> None:
    project_id = _create_project(client)
    client.post(f"/api/projects/{project_id}/requirements", json=requirement_payload(project_id))
    client.post(f"/api/projects/{project_id}/plan")
    client.post(f"/api/projects/{project_id}/generate")
    client.post(f"/api/projects/{project_id}/validate")
    created = client.post(f"/api/projects/{project_id}/optimize")
    assert created.status_code == 200

    fetched = client.get(f"/api/projects/{project_id}/optimization")
    assert fetched.status_code == 200
    assert fetched.json() == created.json()


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
    submit_response = client.post(f"/api/projects/{project_id}/requirements", json=requirement_payload(project_id))
    assert submit_response.status_code == 200
    responses = [
        client.get("/api/projects"),
        client.get(f"/api/projects/{project_id}"),
        client.get(f"/api/projects/{project_id}/requirements"),
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

import pytest

import app.services.repair_service as repair_module
from app.agents import CodeGenerationAgent, PlanningAgent
from app.services.repair_service import RepairService
from app.storage.memory import store


def test_repair_loop_returns_immediately_when_code_is_verified() -> None:
    plan, artifact = save_plan_and_artifact("Motor Control")

    report = RepairService(store).run_repair_loop("PRJ-0421")

    assert report.finalStatus == "VERIFIED"
    assert report.iterations == 1
    assert report.debuggingReports == []
    assert report.finalCodeArtifact.artifactId == artifact.artifactId
    assert report.finalValidationReport.status == "VERIFIED"


def test_motor_missing_emergency_stop_is_repaired_and_verified() -> None:
    plan, artifact = save_plan_and_artifact("Motor Control")
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
    store.save_code_artifact("PRJ-0421", artifact.model_copy(update={"source": unsafe_source}))

    report = RepairService(store).run_repair_loop("PRJ-0421")

    assert report.finalStatus == "VERIFIED"
    assert report.iterations == 2
    assert report.debuggingReports[0].errorType == "motor_safety_shutdown"
    assert report.finalCodeArtifact.metadata.generator == "template_based.repair.v1"
    assert "Safety_OK := E_Stop AND NOT Overload;" in report.finalCodeArtifact.source


def test_traffic_light_conflict_is_repaired() -> None:
    plan, artifact = save_plan_and_artifact("Traffic Control")
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
    store.save_code_artifact("PRJ-0421", artifact.model_copy(update={"source": unsafe_source}))

    report = RepairService(store).run_repair_loop("PRJ-0421")

    assert report.finalStatus == "VERIFIED"
    assert report.debuggingReports[0].errorType == "traffic_conflicting_green"
    assert "Green_Light := NOT Red_Light AND NOT Amber_Light;" in report.finalCodeArtifact.source


def test_invalid_syntax_triggers_debugging_and_regeneration() -> None:
    plan, artifact = save_plan_and_artifact("Motor Control")
    store.save_code_artifact("PRJ-0421", artifact.model_copy(update={"source": artifact.source.replace("END_PROGRAM", "")}))

    report = RepairService(store).run_repair_loop("PRJ-0421")

    assert report.finalStatus == "VERIFIED"
    assert report.validationReports[0].status == "SYNTAX_ERROR"
    assert report.debuggingReports[0].errorType == "missing_end_pou"
    assert "END_PROGRAM" in report.finalCodeArtifact.source


def test_max_iter_stops_infinite_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    plan, artifact = save_plan_and_artifact("Motor Control")
    store.save_code_artifact("PRJ-0421", artifact.model_copy(update={"source": artifact.source.replace("END_PROGRAM", "")}))

    class AlwaysBadGenerator:
        def __init__(self, mode: str = "template_based") -> None:
            self.mode = mode

        def generate_code(self, **kwargs):
            repaired = CodeGenerationAgent(mode="template_based").generate_code(**kwargs)
            return repaired.model_copy(update={"source": repaired.source.replace("END_PROGRAM", "")})

    monkeypatch.setattr(repair_module, "CodeGenerationAgent", AlwaysBadGenerator)

    report = RepairService(store).run_repair_loop("PRJ-0421", max_iter=2)

    assert report.finalStatus == "ITERATION_LIMIT_REACHED"
    assert report.iterations == 2
    assert report.finalValidationReport.status == "SYNTAX_ERROR"


def test_repair_loop_report_is_stored_in_memory() -> None:
    save_plan_and_artifact("Motor Control")

    report = RepairService(store).run_repair_loop("PRJ-0421")

    stored = store.get_repair_loop_report("PRJ-0421")
    assert stored is not None
    assert stored.projectId == report.projectId
    assert stored.finalStatus == "VERIFIED"


def save_plan_and_artifact(domain: str):
    requirements = {
        "Motor Control": "Motor start stop with emergency stop and overload protection.",
        "Traffic Control": "Traffic light controller with pedestrian request.",
    }
    plan = PlanningAgent().generate_plan(
        project_id="PRJ-0421",
        requirement_text=requirements.get(domain, "Generic PLC control requirement."),
        domain=domain,
    )
    artifact = CodeGenerationAgent().generate_code(project_id="PRJ-0421", plan=plan)
    store.save_plan("PRJ-0421", plan)
    store.save_code_artifact("PRJ-0421", artifact)
    return plan, artifact

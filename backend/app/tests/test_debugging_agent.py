import pytest

from app.agents import CodeGenerationAgent, DebuggingAgent, PlanningAgent, ValidationAgent

pytestmark = pytest.mark.asyncio


async def test_verified_validation_returns_not_required() -> None:
    plan, artifact, validation = await validated_artifacts("PRJ-MOTOR", "Motor Control")

    report = await DebuggingAgent().debug(project_id="PRJ-MOTOR", plan=plan, artifact=artifact, validation=validation)

    assert report.status == "NOT_REQUIRED"
    assert report.sourceValidationStatus == "CHECKS_PASSED"
    assert "No debugging required" in report.rootCauseSummary


async def test_syntax_error_missing_end_program_returns_patch_advice() -> None:
    plan, artifact, _ = await validated_artifacts("PRJ-MOTOR", "Motor Control")
    validation = ValidationAgent().validate(
        project_id="PRJ-MOTOR",
        artifact=artifact.model_copy(update={"source": artifact.source.replace("END_PROGRAM", "")}),
        plan=plan,
    )

    report = await DebuggingAgent().debug(project_id="PRJ-MOTOR", plan=plan, artifact=artifact, validation=validation)

    assert report.status == "PATCH_ADVICE_GENERATED"
    assert report.errorType == "missing_end_pou"
    assert "END_PROGRAM" in " ".join(report.patchAdvice)


async def test_undeclared_variable_error_returns_targeted_advice() -> None:
    plan, artifact, _ = await validated_artifacts("PRJ-GENERIC", "Packaging")
    invalid_source = artifact.source.replace("Process_Enable := Run_State AND NOT Fault_State;", "Ghost_Output := TRUE;")
    validation = ValidationAgent().validate(
        project_id="PRJ-GENERIC",
        artifact=artifact.model_copy(update={"source": invalid_source}),
        plan=plan,
    )

    report = await DebuggingAgent().debug(project_id="PRJ-GENERIC", plan=plan, artifact=artifact, validation=validation)

    assert report.errorType == "undeclared_assigned_variable"
    assert "Ghost_Output" in report.rootCauseSummary
    assert any("Declare Ghost_Output" in item for item in report.patchAdvice)


async def test_motor_formal_violation_returns_shutdown_patch_advice() -> None:
    plan, artifact, _ = await validated_artifacts("PRJ-MOTOR", "Motor Control")
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
    validation = ValidationAgent().validate(
        project_id="PRJ-MOTOR",
        artifact=artifact.model_copy(update={"source": unsafe_source}),
        plan=plan,
    )

    report = await DebuggingAgent().debug(project_id="PRJ-MOTOR", plan=plan, artifact=artifact, validation=validation)

    assert report.errorType == "motor_safety_shutdown"
    assert "emergency stop" in report.rootCauseSummary.lower()
    assert any("Safety_OK" in item for item in report.patchAdvice)


async def test_traffic_formal_violation_returns_conflicting_green_advice() -> None:
    plan, artifact, _ = await validated_artifacts("PRJ-TRAFFIC", "Traffic Control")
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
    validation = ValidationAgent().validate(
        project_id="PRJ-TRAFFIC",
        artifact=artifact.model_copy(update={"source": unsafe_source}),
        plan=plan,
    )

    report = await DebuggingAgent().debug(project_id="PRJ-TRAFFIC", plan=plan, artifact=artifact, validation=validation)

    assert report.errorType == "traffic_conflicting_green"
    assert any("Ped_Walk" in item for item in report.patchAdvice)


async def test_tank_formal_violation_returns_high_low_safety_advice() -> None:
    plan, artifact, _ = await validated_artifacts("PRJ-TANK", "Process Control")
    unsafe_source = """PROGRAM Tank_Controller
VAR_INPUT
    Level_PV : REAL;
    Low_SP : REAL;
    High_SP : REAL;
    HighHigh_SP : REAL;
    Auto_Mode : BOOL;
END_VAR
VAR_OUTPUT
    Inlet_Valve : BOOL;
    Outlet_Valve : BOOL;
    High_Alarm : BOOL;
END_VAR
Inlet_Valve := TRUE;
Outlet_Valve := FALSE;
High_Alarm := FALSE;
END_PROGRAM"""
    validation = ValidationAgent().validate(
        project_id="PRJ-TANK",
        artifact=artifact.model_copy(update={"source": unsafe_source}),
        plan=plan,
    )

    report = await DebuggingAgent().debug(project_id="PRJ-TANK", plan=plan, artifact=artifact, validation=validation)

    assert report.errorType == "tank_level_safety"
    assert any("High_SP" in item or "Low_SP" in item for item in report.patchAdvice)


async def test_timeout_returns_cannot_debug() -> None:
    plan, artifact, validation = await validated_artifacts("PRJ-MOTOR", "Motor Control")
    timeout_report = validation.model_copy(update={
        "status": "TIMEOUT",
        "summary": "Formal solver timed out.",
        "syntaxPassed": True,
        "formalPassed": False,
    })

    report = await DebuggingAgent().debug(project_id="PRJ-MOTOR", plan=plan, artifact=artifact, validation=timeout_report)

    assert report.status == "CANNOT_DEBUG"
    assert report.errorType == "verification_timeout"
    assert "Reduce code complexity" in " ".join(report.patchAdvice)


async def test_llm_mode_falls_back_to_rule_based() -> None:
    plan, artifact, validation = await validated_artifacts("PRJ-MOTOR", "Motor Control")

    report = await DebuggingAgent(mode="llm").debug(
        project_id="PRJ-MOTOR",
        plan=plan,
        artifact=artifact,
        validation=validation,
    )
    assert report.status == "NOT_REQUIRED"


async def validated_artifacts(project_id: str, domain: str):
    requirements = {
        "Motor Control": "Motor start stop with emergency stop and overload protection.",
        "Traffic Control": "Traffic light controller with pedestrian request.",
        "Process Control": "Tank level control with high high trip and inlet valve.",
        "Packaging": "Coordinate a generic process enable with reset.",
    }
    plan = await PlanningAgent().generate_plan(
        project_id=project_id,
        requirement_text=requirements.get(domain, "Generic PLC control requirement."),
        domain=domain,
    )
    artifact = await CodeGenerationAgent().generate_code(project_id=project_id, plan=plan)
    validation = ValidationAgent().validate(project_id=project_id, artifact=artifact, plan=plan)
    return plan, artifact, validation

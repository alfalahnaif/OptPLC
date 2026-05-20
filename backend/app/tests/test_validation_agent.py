import pytest

from app.agents import CodeGenerationAgent, PlanningAgent, ValidationAgent


def test_valid_motor_structured_text_returns_verified() -> None:
    plan = PlanningAgent().generate_plan(
        project_id="PRJ-MOTOR",
        requirement_text="Motor start stop with emergency stop and overload protection.",
        domain="Motor Control",
    )
    artifact = CodeGenerationAgent().generate_code(project_id="PRJ-MOTOR", plan=plan)

    report = ValidationAgent().validate(project_id="PRJ-MOTOR", artifact=artifact, plan=plan)

    assert report.status == "VERIFIED"
    assert report.syntaxPassed is True
    assert report.formalPassed is True
    assert report.validator == "static.v1"


def test_motor_missing_emergency_stop_handling_returns_formal_violation() -> None:
    plan = PlanningAgent().generate_plan(
        project_id="PRJ-MOTOR",
        requirement_text="Motor start stop with emergency stop and overload protection.",
        domain="Motor Control",
    )
    artifact = CodeGenerationAgent().generate_code(project_id="PRJ-MOTOR", plan=plan)
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

    report = ValidationAgent().validate(
        project_id="PRJ-MOTOR",
        artifact=artifact.model_copy(update={"source": unsafe_source}),
        plan=plan,
    )

    assert report.status == "FORMAL_VIOLATION"
    assert report.syntaxPassed is True
    assert report.formalPassed is False
    assert any(result.id == "MC-1" and result.status == "failed" for result in report.safetyResults)


def test_invalid_structured_text_missing_end_program_returns_syntax_error() -> None:
    plan = PlanningAgent().generate_plan(
        project_id="PRJ-MOTOR",
        requirement_text="Motor start stop with emergency stop and overload protection.",
        domain="Motor Control",
    )
    artifact = CodeGenerationAgent().generate_code(project_id="PRJ-MOTOR", plan=plan)

    report = ValidationAgent().validate(
        project_id="PRJ-MOTOR",
        artifact=artifact.model_copy(update={"source": artifact.source.replace("END_PROGRAM", "")}),
        plan=plan,
    )

    assert report.status == "SYNTAX_ERROR"
    assert any("END_PROGRAM" in error for error in report.syntaxErrors)


def test_undeclared_assigned_variable_returns_syntax_error() -> None:
    plan = PlanningAgent().generate_plan(
        project_id="PRJ-GENERIC",
        requirement_text="Generic process enable with reset.",
        domain="Packaging",
    )
    artifact = CodeGenerationAgent().generate_code(project_id="PRJ-GENERIC", plan=plan)
    invalid_source = artifact.source.replace("Process_Enable := Run_State AND NOT Fault_State;", "Ghost_Output := TRUE;")

    report = ValidationAgent().validate(
        project_id="PRJ-GENERIC",
        artifact=artifact.model_copy(update={"source": invalid_source}),
        plan=plan,
    )

    assert report.status == "SYNTAX_ERROR"
    assert "Ghost_Output" in " ".join(report.syntaxErrors)


def test_traffic_conflicting_greens_return_formal_violation() -> None:
    plan = PlanningAgent().generate_plan(
        project_id="PRJ-TRAFFIC",
        requirement_text="Traffic light controller with pedestrian request.",
        domain="Traffic Control",
    )
    artifact = CodeGenerationAgent().generate_code(project_id="PRJ-TRAFFIC", plan=plan)
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

    report = ValidationAgent().validate(
        project_id="PRJ-TRAFFIC",
        artifact=artifact.model_copy(update={"source": unsafe_source}),
        plan=plan,
    )

    assert report.status == "FORMAL_VIOLATION"
    assert any(result.id == "TL-1" and result.status == "failed" for result in report.safetyResults)


def test_tank_level_with_real_variables_and_safety_logic_returns_verified() -> None:
    plan = PlanningAgent().generate_plan(
        project_id="PRJ-TANK",
        requirement_text="Tank level control with high high trip and inlet valve.",
        domain="Process Control",
    )
    artifact = CodeGenerationAgent().generate_code(project_id="PRJ-TANK", plan=plan)

    report = ValidationAgent().validate(project_id="PRJ-TANK", artifact=artifact, plan=plan)

    assert report.status == "VERIFIED"
    assert all(result.status == "passed" for result in report.safetyResults)


def test_formal_mode_is_placeholder_only() -> None:
    plan = PlanningAgent().generate_plan(
        project_id="PRJ-MOTOR",
        requirement_text="Motor start stop.",
        domain="Motor Control",
    )
    artifact = CodeGenerationAgent().generate_code(project_id="PRJ-MOTOR", plan=plan)

    with pytest.raises(NotImplementedError, match="future MATIEC/nuXmv/PLCverif"):
        ValidationAgent(mode="formal").validate(project_id="PRJ-MOTOR", artifact=artifact, plan=plan)

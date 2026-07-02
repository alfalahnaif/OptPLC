import pytest

from app.agents import CodeGenerationAgent, PlanningAgent, ValidationAgent
from app.services.validation_service import MatiecValidator

pytestmark = pytest.mark.asyncio


async def test_valid_motor_structured_text_returns_verified() -> None:
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-MOTOR",
        requirement_text="Motor start stop with emergency stop and overload protection.",
        domain="Motor Control",
    )
    artifact = await CodeGenerationAgent().generate_code(project_id="PRJ-MOTOR", plan=plan)

    report = ValidationAgent().validate(project_id="PRJ-MOTOR", artifact=artifact, plan=plan)

    assert report.status == "VERIFIED"
    assert report.syntaxPassed is True
    assert report.formalPassed is True
    assert report.validator == "static.v1"


async def test_motor_missing_emergency_stop_handling_returns_formal_violation() -> None:
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-MOTOR",
        requirement_text="Motor start stop with emergency stop and overload protection.",
        domain="Motor Control",
    )
    artifact = await CodeGenerationAgent().generate_code(project_id="PRJ-MOTOR", plan=plan)
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


async def test_motor_stop_pb_open_circuit_behavior_returns_formal_violation() -> None:
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-MOTOR",
        requirement_text="Motor start stop with emergency stop and overload protection and reset pushbutton.",
        domain="Motor Control",
    )
    artifact = await CodeGenerationAgent().generate_code(project_id="PRJ-MOTOR", plan=plan)
    unsafe_source = """PROGRAM Motor_Controller
VAR_INPUT
    Start_PB : BOOL;
    Stop_PB : BOOL;
    Emergency_Stop : BOOL;
    Overload : BOOL;
    Reset_PB : BOOL;
END_VAR
VAR_OUTPUT
    Motor_Run : BOOL;
END_VAR
VAR
    Run_Cmd : BOOL;
    Fault_State : BOOL;
    Safety_OK : BOOL;
END_VAR
Safety_OK := Emergency_Stop AND NOT Overload;
IF Start_PB AND NOT Stop_PB AND NOT Fault_State THEN
    Run_Cmd := TRUE;
END_IF;
IF Stop_PB OR Fault_State THEN
    Run_Cmd := FALSE;
END_IF;
Motor_Run := Run_Cmd AND Safety_OK AND NOT Fault_State;
END_PROGRAM"""

    report = ValidationAgent().validate(
        project_id="PRJ-MOTOR",
        artifact=artifact.model_copy(update={"source": unsafe_source}),
        plan=plan,
    )

    assert report.status == "FORMAL_VIOLATION"
    assert any(result.id == "MC-4" and result.status == "failed" for result in report.safetyResults)


async def test_invalid_structured_text_missing_end_program_returns_syntax_error() -> None:
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-MOTOR",
        requirement_text="Motor start stop with emergency stop and overload protection.",
        domain="Motor Control",
    )
    artifact = await CodeGenerationAgent().generate_code(project_id="PRJ-MOTOR", plan=plan)

    report = ValidationAgent().validate(
        project_id="PRJ-MOTOR",
        artifact=artifact.model_copy(update={"source": artifact.source.replace("END_PROGRAM", "")}),
        plan=plan,
    )

    assert report.status == "SYNTAX_ERROR"
    assert any("END_PROGRAM" in error for error in report.syntaxErrors)


async def test_undeclared_assigned_variable_returns_syntax_error() -> None:
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-GENERIC",
        requirement_text="Generic process enable with reset.",
        domain="Packaging",
    )
    artifact = await CodeGenerationAgent().generate_code(project_id="PRJ-GENERIC", plan=plan)
    invalid_source = artifact.source.replace("Process_Enable := Run_State AND NOT Fault_State;", "Ghost_Output := TRUE;")

    report = ValidationAgent().validate(
        project_id="PRJ-GENERIC",
        artifact=artifact.model_copy(update={"source": invalid_source}),
        plan=plan,
    )

    assert report.status == "SYNTAX_ERROR"
    assert "Ghost_Output" in " ".join(report.syntaxErrors)


async def test_traffic_conflicting_greens_return_formal_violation() -> None:
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-TRAFFIC",
        requirement_text="Traffic light controller with pedestrian request.",
        domain="Traffic Control",
    )
    artifact = await CodeGenerationAgent().generate_code(project_id="PRJ-TRAFFIC", plan=plan)
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


async def test_tank_level_with_real_variables_and_safety_logic_returns_verified() -> None:
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-TANK",
        requirement_text="Tank level control with high high trip and inlet valve.",
        domain="Process Control",
    )
    artifact = await CodeGenerationAgent().generate_code(project_id="PRJ-TANK", plan=plan)

    report = ValidationAgent().validate(project_id="PRJ-TANK", artifact=artifact, plan=plan)

    assert report.status == "VERIFIED"
    assert all(result.status == "passed" for result in report.safetyResults)


async def test_formal_mode_is_placeholder_only() -> None:
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-MOTOR",
        requirement_text="Motor start stop.",
        domain="Motor Control",
    )
    artifact = await CodeGenerationAgent().generate_code(project_id="PRJ-MOTOR", plan=plan)

    with pytest.raises(NotImplementedError, match="future MATIEC/nuXmv/PLCverif"):
        ValidationAgent(mode="formal").validate(project_id="PRJ-MOTOR", artifact=artifact, plan=plan)


async def test_matiec_success_path_keeps_static_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-MOTOR",
        requirement_text="Motor start stop with emergency stop and overload protection.",
        domain="Motor Control",
    )
    artifact = await CodeGenerationAgent().generate_code(project_id="PRJ-MOTOR", plan=plan)
    agent = ValidationAgent(matiec_validator=MatiecValidator())
    monkeypatch.setattr(ValidationAgent, "_is_matiec_available", staticmethod(lambda: (True, "ok")))
    monkeypatch.setattr(
        ValidationAgent,
        "_run_matiec_syntax",
        lambda self, _source: {"passed": True, "errors": [], "raw_output": ""},
    )

    report = agent.validate(project_id="PRJ-MOTOR", artifact=artifact, plan=plan)

    assert report.status == "VERIFIED"
    assert report.syntaxPassed is True


async def test_matiec_syntax_failure_returns_syntax_error(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-MOTOR",
        requirement_text="Motor start stop with emergency stop and overload protection.",
        domain="Motor Control",
    )
    artifact = await CodeGenerationAgent().generate_code(project_id="PRJ-MOTOR", plan=plan)
    agent = ValidationAgent(matiec_validator=MatiecValidator())
    monkeypatch.setattr(ValidationAgent, "_is_matiec_available", staticmethod(lambda: (True, "ok")))
    monkeypatch.setattr(
        ValidationAgent,
        "_run_matiec_syntax",
        lambda self, _source: {
            "passed": False,
            "errors": ["matiec: syntax error near END_IF"],
            "raw_output": "error: syntax",
        },
    )

    report = agent.validate(project_id="PRJ-MOTOR", artifact=artifact, plan=plan)

    assert report.status == "SYNTAX_ERROR"
    assert any("matiec: syntax error" in item for item in report.syntaxErrors)


async def test_matiec_unavailable_falls_back_to_static_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-MOTOR",
        requirement_text="Motor start stop with emergency stop and overload protection.",
        domain="Motor Control",
    )
    artifact = await CodeGenerationAgent().generate_code(project_id="PRJ-MOTOR", plan=plan)
    agent = ValidationAgent(matiec_validator=MatiecValidator())
    monkeypatch.setattr(ValidationAgent, "_is_matiec_available", staticmethod(lambda: (False, "missing binary")))
    monkeypatch.setattr(
        ValidationAgent,
        "_run_matiec_syntax",
        lambda self, _source: (_ for _ in ()).throw(AssertionError("MATIEC should not run when unavailable")),
    )

    report = agent.validate(project_id="PRJ-MOTOR", artifact=artifact, plan=plan)

    assert report.status == "VERIFIED"
    assert report.syntaxPassed is True


async def test_matiec_timeout_falls_back_to_static_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-MOTOR",
        requirement_text="Motor start stop with emergency stop and overload protection.",
        domain="Motor Control",
    )
    artifact = await CodeGenerationAgent().generate_code(project_id="PRJ-MOTOR", plan=plan)
    agent = ValidationAgent(matiec_validator=MatiecValidator())
    monkeypatch.setattr(ValidationAgent, "_is_matiec_available", staticmethod(lambda: (True, "ok")))
    monkeypatch.setattr(
        ValidationAgent,
        "_run_matiec_syntax",
        lambda self, _source: {
            "passed": False,
            "errors": ["MATIEC syntax validation timed out after 30 seconds."],
            "raw_output": "",
        },
    )

    report = agent.validate(project_id="PRJ-MOTOR", artifact=artifact, plan=plan)

    assert report.status == "VERIFIED"
    assert report.syntaxPassed is True

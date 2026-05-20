import pytest

from app.agents import CodeGenerationAgent, PlanningAgent


def test_motor_plan_generates_structured_text_program() -> None:
    plan = PlanningAgent().generate_plan(
        project_id="PRJ-MOTOR",
        requirement_text="Motor start stop with emergency stop and overload protection.",
        domain="Motor Control",
    )

    artifact = CodeGenerationAgent().generate_code(project_id="PRJ-MOTOR", plan=plan)

    assert artifact.language == "structured-text"
    assert artifact.metadata.generator == "template_based.v1"
    assert "PROGRAM PLC_PRJ_MOTOR_Controller" in artifact.source
    assert "VAR_INPUT" in artifact.source
    assert "VAR_OUTPUT" in artifact.source
    assert "END_PROGRAM" in artifact.source
    assert "Motor_Run := Run_Cmd AND Safety_OK AND NOT Fault_State;" in artifact.source


def test_traffic_light_generation_avoids_conflicting_green_outputs() -> None:
    plan = PlanningAgent().generate_plan(
        project_id="PRJ-TRAFFIC",
        requirement_text="Traffic light controller with vehicle detector and pedestrian request.",
        domain="Traffic Control",
    )

    source = CodeGenerationAgent().generate_code(project_id="PRJ-TRAFFIC", plan=plan).source

    assert "Green_Light := NOT Red_Light AND NOT Amber_Light;" in source
    assert "Ped_Walk := Red_Light AND Ped_Request;" in source
    assert "Green_Light := TRUE" not in source


def test_tank_level_generation_includes_real_variables() -> None:
    plan = PlanningAgent().generate_plan(
        project_id="PRJ-TANK",
        requirement_text="Tank level control with high high trip and inlet valve.",
        domain="Process Control",
    )

    source = CodeGenerationAgent().generate_code(project_id="PRJ-TANK", plan=plan).source

    assert "Level_PV : REAL;" in source
    assert "Low_SP : REAL;" in source
    assert "High_SP : REAL;" in source
    assert "High_Trip := Level_PV >= HighHigh_SP;" in source


def test_safety_interlock_generation_fails_safe() -> None:
    plan = PlanningAgent().generate_plan(
        project_id="PRJ-SAFE",
        requirement_text="Safety interlock for a guarded press.",
        domain="Safety Interlocks",
    )

    source = CodeGenerationAgent().generate_code(project_id="PRJ-SAFE", plan=plan).source

    assert "Permissive_OK := Guard_Closed" in source
    assert "Machine_Enable := Permissive_OK AND NOT Trip_State;" in source


def test_batch_generation_includes_step_logic() -> None:
    plan = PlanningAgent().generate_plan(
        project_id="PRJ-BATCH",
        requirement_text="Sequential batch reactor fill heat mix and drain.",
        domain="Sequential Batch",
    )

    source = CodeGenerationAgent().generate_code(project_id="PRJ-BATCH", plan=plan).source

    assert "Step : INT;" in source
    assert "CASE Step OF" in source
    assert "Fill_Valve := Step = 10;" in source


def test_generic_plan_generates_structured_fallback() -> None:
    plan = PlanningAgent().generate_plan(
        project_id="PRJ-GENERIC",
        requirement_text="Coordinate a generic process enable with reset.",
        domain="Packaging",
    )

    source = CodeGenerationAgent().generate_code(project_id="PRJ-GENERIC", plan=plan).source

    assert "PROGRAM PLC_PRJ_GENERIC_Controller" in source
    assert "VAR_INPUT" in source
    assert "Process_Enable := Run_State AND NOT Fault_State;" in source
    assert "END_PROGRAM" in source


def test_llm_mode_is_placeholder_only() -> None:
    plan = PlanningAgent().generate_plan(
        project_id="PRJ-LLM",
        requirement_text="Motor start stop.",
        domain="Motor Control",
    )

    with pytest.raises(NotImplementedError, match="reserved for future integration"):
        CodeGenerationAgent(mode="llm").generate_code(project_id="PRJ-LLM", plan=plan)


import pytest

from app.agents import CodeGenerationAgent, PlanningAgent
from app.schemas.contracts import PlanObject, PlanScope, PlanSignal

pytestmark = pytest.mark.asyncio


async def test_motor_plan_generates_structured_text_program() -> None:
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-MOTOR",
        requirement_text="Motor start stop with emergency stop and overload protection.",
        domain="Motor Control",
    )

    artifact = await CodeGenerationAgent().generate_code(project_id="PRJ-MOTOR", plan=plan)

    assert artifact.language == "structured-text"
    assert artifact.metadata.generator == "template_based.v1"
    assert "PROGRAM PLC_PRJ_MOTOR_Controller" in artifact.source
    assert "VAR_INPUT" in artifact.source
    assert "VAR_OUTPUT" in artifact.source
    assert "END_PROGRAM" in artifact.source
    assert "Motor_Run := Run_Cmd AND Safety_OK AND NOT Fault_State;" in artifact.source


async def test_traffic_light_generation_avoids_conflicting_green_outputs() -> None:
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-TRAFFIC",
        requirement_text="Traffic light controller with vehicle detector and pedestrian request.",
        domain="Traffic Control",
    )

    source = (await CodeGenerationAgent().generate_code(project_id="PRJ-TRAFFIC", plan=plan)).source

    assert "Green_Light := NOT Red_Light AND NOT Amber_Light;" in source
    assert "Ped_Walk := Red_Light AND Ped_Request;" in source
    assert "Green_Light := TRUE" not in source


async def test_tank_level_generation_includes_real_variables() -> None:
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-TANK",
        requirement_text="Tank level control with high high trip and inlet valve.",
        domain="Process Control",
    )

    source = (await CodeGenerationAgent().generate_code(project_id="PRJ-TANK", plan=plan)).source

    assert "Level_PV : REAL;" in source
    assert "Low_SP : REAL;" in source
    assert "High_SP : REAL;" in source
    assert "High_Trip := Level_PV >= HighHigh_SP;" in source


async def test_safety_interlock_generation_fails_safe() -> None:
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-SAFE",
        requirement_text="Safety interlock for a guarded press.",
        domain="Safety Interlocks",
    )

    source = (await CodeGenerationAgent().generate_code(project_id="PRJ-SAFE", plan=plan)).source

    assert "Permissive_OK := Guard_Closed" in source
    assert "Machine_Enable := Permissive_OK AND NOT Trip_State;" in source


async def test_batch_generation_includes_step_logic() -> None:
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-BATCH",
        requirement_text="Sequential batch reactor fill heat mix and drain, then mark batch complete.",
        domain="Sequential Batch",
    )

    source = (await CodeGenerationAgent().generate_code(project_id="PRJ-BATCH", plan=plan)).source

    assert "Step_State : INT;" in source
    assert "Fault_State : BOOL;" in source
    assert "CASE Step_State OF" in source
    assert "Fill_Valve := (Step_State = 10) AND NOT Fault_State;" in source
    assert "Mixer_Motor := (Step_State = 20) AND NOT Fault_State;" in source
    assert "Drain_Valve := (Step_State = 30) AND NOT Fault_State;" in source
    assert "Batch_Complete := (Step_State = 40) AND NOT Fault_State;" in source
    assert "IF NOT Emergency_Stop OR Abort_PB THEN" in source
    assert "IF Fault_State AND Reset_PB AND Emergency_Stop AND NOT Abort_PB THEN" in source
    assert "Motor_Run" not in source
    assert "Stop_PB" not in source


async def test_generic_plan_generates_structured_fallback() -> None:
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-GENERIC",
        requirement_text="Coordinate a generic process enable with reset.",
        domain="Packaging",
    )

    source = (await CodeGenerationAgent().generate_code(project_id="PRJ-GENERIC", plan=plan)).source

    assert "PROGRAM PLC_PRJ_GENERIC_Controller" in source
    assert "VAR_INPUT" in source
    assert "Process_Enable := Run_State AND NOT Fault_State;" in source
    assert "END_PROGRAM" in source


async def test_llm_mode_is_placeholder_only() -> None:
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-LLM",
        requirement_text="Motor start stop.",
        domain="Motor Control",
    )

    with pytest.raises(NotImplementedError, match="reserved for future integration"):
        await CodeGenerationAgent(mode="llm").generate_code(project_id="PRJ-LLM", plan=plan)


async def test_motor_template_uses_normally_closed_stop_pb_semantics() -> None:
    plan = PlanObject(
        projectId="PRJ-MOTOR-NC",
        domain="Motor Control",
        agent="PlanningAgent/rule_based.v1",
        generatedAt="2026-05-21T09:00:00Z",
        inputs=[
            PlanSignal(name="Start_PB", type="BOOL", source="DI-01", description="Start pushbutton"),
            PlanSignal(name="Stop_PB", type="BOOL", source="DI-02", description="Stop pushbutton"),
            PlanSignal(name="Emergency_Stop", type="BOOL", source="DI-03", description="Emergency stop"),
            PlanSignal(name="Overload", type="BOOL", source="DI-04", description="Overload"),
            PlanSignal(name="Reset_PB", type="BOOL", source="DI-05", description="Reset pushbutton"),
        ],
        outputs=[
            PlanSignal(name="Motor_Run", type="BOOL", address="DO-01", description="Motor output"),
        ],
        logicRules=[],
        safetyConstraints=[],
        scope=PlanScope(
            standard="IEC 61131-3",
            edition="3rd ed. (2013)",
            language="Structured Text",
            runtime="CODESYS / TwinCAT compatible",
        ),
    )

    source = (await CodeGenerationAgent().generate_code(project_id="PRJ-MOTOR-NC", plan=plan)).source

    assert "Start_PB AND Stop_PB" in source
    assert "IF NOT Stop_PB OR Fault_State OR NOT Safety_OK THEN" in source
    assert "Start_PB AND NOT Stop_PB" not in source
    assert "IF Stop_PB OR Fault_State" not in source
    assert "Stop_PB : BOOL;  (* Normally closed stop pushbutton: TRUE = healthy, FALSE = pressed *)" in source


async def test_different_domains_produce_different_code() -> None:
    motor_plan = await PlanningAgent().generate_plan(
        project_id="PRJ-DIFF-MOTOR",
        requirement_text="Motor control with start stop and emergency stop.",
        domain="Motor Control",
    )
    batch_plan = await PlanningAgent().generate_plan(
        project_id="PRJ-DIFF-BATCH",
        requirement_text="Sequential batch process with fill, mix, drain and reset.",
        domain="Sequential Batch",
    )

    motor_source = (await CodeGenerationAgent().generate_code(project_id="PRJ-DIFF-MOTOR", plan=motor_plan)).source
    batch_source = (await CodeGenerationAgent().generate_code(project_id="PRJ-DIFF-BATCH", plan=batch_plan)).source

    assert "Motor_Run := Run_Cmd AND Safety_OK AND NOT Fault_State;" in motor_source
    assert "CASE Step_State OF" in batch_source
    assert motor_source != batch_source


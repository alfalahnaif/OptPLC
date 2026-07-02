import pytest

from app.agents import PlanningAgent

pytestmark = pytest.mark.asyncio


async def test_motor_requirement_returns_motor_plan() -> None:
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-MOTOR",
        requirement_text="Motor start stop with emergency stop and overload protection.",
        safety_constraints=["Motor must not auto-restart after E-stop"],
        domain="Motor Control",
        complexity_tier="medium",
    )

    assert plan.projectId == "PRJ-MOTOR"
    assert {signal.name for signal in plan.inputs} >= {"Start_PB", "Stop_PB", "Emergency_Stop", "Overload"}
    assert "Reset_PB" not in {signal.name for signal in plan.inputs}
    assert {signal.name for signal in plan.outputs} >= {"Motor_Run"}
    assert any("Fault_State" in rule for rule in plan.logicRules)
    assert "Motor must not auto-restart after Emergency_Stop" in plan.safetyConstraints


async def test_motor_requirement_with_reset_mentions_reset_input() -> None:
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-MOTOR",
        requirement_text="Motor start stop with emergency stop, overload and reset pushbutton.",
        safety_constraints=["Reset is required after emergency stop."],
        domain="Motor Control",
        complexity_tier="medium",
    )
    assert "Reset_PB" in {signal.name for signal in plan.inputs}


async def test_traffic_light_requirement_returns_signal_plan() -> None:
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-TRAFFIC",
        requirement_text="Intersection traffic light controller with pedestrian request.",
        domain="Traffic Control",
    )

    assert {signal.name for signal in plan.inputs} >= {"Vehicle_Detect", "Ped_Request", "Cycle_Timer"}
    assert {signal.name for signal in plan.outputs} >= {"Red_Light", "Amber_Light", "Green_Light", "Ped_Walk"}


async def test_tank_level_requirement_uses_real_variables() -> None:
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-TANK",
        requirement_text="Tank level control with high high trip and inlet valve.",
        domain="Process Control",
    )

    real_inputs = {signal.name for signal in plan.inputs if signal.type == "REAL"}
    assert real_inputs >= {"Level_PV", "Low_SP", "High_SP"}
    assert {signal.name for signal in plan.outputs} >= {"Inlet_Valve", "Outlet_Valve", "High_Alarm"}


async def test_safety_interlock_requirement_returns_interlock_plan() -> None:
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-SAFE",
        requirement_text="Safety interlock for a guarded press with two hand controls.",
        domain="Safety Interlocks",
    )

    assert {signal.name for signal in plan.inputs} >= {"Guard_Closed", "TwoHand_Left", "TwoHand_Right", "Reset_PB"}
    assert {signal.name for signal in plan.outputs} >= {"Machine_Enable", "Trip_Lamp", "Alarm_Horn"}


async def test_sequential_batch_requirement_returns_batch_plan() -> None:
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-BATCH",
        requirement_text="Sequential batch reactor with Fill_Valve, Mixer_Motor, Drain_Valve, Batch_Complete, emergency stop, and reset.",
        domain="Sequential Batch",
    )

    input_names = {signal.name for signal in plan.inputs}
    output_names = {signal.name for signal in plan.outputs}
    logic_text = " ".join(plan.logicRules)

    assert input_names >= {"Start_PB", "Emergency_Stop", "Abort_PB", "Reset_PB", "High_Level", "Low_Level", "Mix_Timer_Done"}
    assert output_names >= {"Fill_Valve", "Mixer_Motor", "Drain_Valve", "Batch_Complete"}
    assert "Motor_Run" not in output_names
    assert "Stop_PB" not in input_names
    assert "Fill step" in logic_text
    assert "Mix step" in logic_text
    assert "Drain step" in logic_text
    assert "Emergency/abort shutdown" in logic_text
    assert "Reset after fault" in logic_text
    assert "Return to idle after complete" in logic_text


async def test_sequential_batch_uses_confirmed_outputs_when_provided() -> None:
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-BATCH-CONFIRMED",
        requirement_text="Sequential batch reactor with emergency stop and reset.",
        confirmed_outputs=["Fill_Valve", "Mixer_Motor", "Drain_Valve", "Batch_Complete"],
        domain="Sequential Batch",
    )
    assert {signal.name for signal in plan.outputs} >= {"Fill_Valve", "Mixer_Motor", "Drain_Valve", "Batch_Complete"}


async def test_sequential_batch_omits_motor_run_unless_explicitly_mentioned() -> None:
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-BATCH-NO-MOTOR",
        requirement_text="Sequential batch reactor with Fill_Valve, Mixer_Motor, Drain_Valve, and Batch_Complete.",
        domain="Sequential Batch",
    )
    assert "Motor_Run" not in {signal.name for signal in plan.outputs}


async def test_sequential_batch_can_include_motor_run_when_explicitly_mentioned() -> None:
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-BATCH-WITH-MOTOR",
        requirement_text="Sequential batch reactor with Motor_Run, Fill_Valve, Mixer_Motor, Drain_Valve, and Batch_Complete.",
        domain="Sequential Batch",
    )
    assert "Motor_Run" in {signal.name for signal in plan.outputs}


async def test_unsupported_domain_returns_generic_valid_plan() -> None:
    plan = await PlanningAgent().generate_plan(
        project_id="PRJ-GENERIC",
        requirement_text="Coordinate a generic industrial process enable with manual reset.",
        domain="Packaging",
    )

    assert plan.inputs
    assert plan.outputs
    assert plan.scope.standard == "IEC 61131-3"
    assert plan.scope.language == "Structured Text"
    assert {signal.name for signal in plan.inputs} >= {"Start_Cmd", "Stop_Cmd", "Reset_Cmd"}


async def test_blank_requirement_is_rejected() -> None:
    with pytest.raises(ValueError, match="Requirement text must not be empty"):
        await PlanningAgent().generate_plan(
            project_id="PRJ-BLANK",
            requirement_text="   ",
            domain="Motor Control",
        )


async def test_llm_mode_is_placeholder_only() -> None:
    with pytest.raises(NotImplementedError, match="reserved for future integration"):
        await PlanningAgent(mode="llm").generate_plan(
            project_id="PRJ-LLM",
            requirement_text="Motor start stop.",
            domain="Motor Control",
        )


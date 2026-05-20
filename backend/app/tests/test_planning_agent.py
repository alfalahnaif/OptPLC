import pytest

from app.agents import PlanningAgent


def test_motor_requirement_returns_motor_plan() -> None:
    plan = PlanningAgent().generate_plan(
        project_id="PRJ-MOTOR",
        requirement_text="Motor start stop with emergency stop and overload protection.",
        safety_constraints=["Motor must not auto-restart after E-stop"],
        domain="Motor Control",
        complexity_tier="medium",
    )

    assert plan.projectId == "PRJ-MOTOR"
    assert {signal.name for signal in plan.inputs} >= {"Start_PB", "Stop_PB", "E_Stop", "Overload", "Reset_PB"}
    assert {signal.name for signal in plan.outputs} >= {"Motor_Run", "Fault_Lamp", "Ready_Lamp"}
    assert any("Fault_State" in rule for rule in plan.logicRules)
    assert "Motor must not auto-restart after E-stop" in plan.safetyConstraints


def test_traffic_light_requirement_returns_signal_plan() -> None:
    plan = PlanningAgent().generate_plan(
        project_id="PRJ-TRAFFIC",
        requirement_text="Intersection traffic light controller with pedestrian request.",
        domain="Traffic Control",
    )

    assert {signal.name for signal in plan.inputs} >= {"Vehicle_Detect", "Ped_Request", "Cycle_Timer"}
    assert {signal.name for signal in plan.outputs} >= {"Red_Light", "Amber_Light", "Green_Light", "Ped_Walk"}


def test_tank_level_requirement_uses_real_variables() -> None:
    plan = PlanningAgent().generate_plan(
        project_id="PRJ-TANK",
        requirement_text="Tank level control with high high trip and inlet valve.",
        domain="Process Control",
    )

    real_inputs = {signal.name for signal in plan.inputs if signal.type == "REAL"}
    assert real_inputs >= {"Level_PV", "Low_SP", "High_SP"}
    assert {signal.name for signal in plan.outputs} >= {"Inlet_Valve", "Outlet_Valve", "High_Alarm"}


def test_safety_interlock_requirement_returns_interlock_plan() -> None:
    plan = PlanningAgent().generate_plan(
        project_id="PRJ-SAFE",
        requirement_text="Safety interlock for a guarded press with two hand controls.",
        domain="Safety Interlocks",
    )

    assert {signal.name for signal in plan.inputs} >= {"Guard_Closed", "TwoHand_Left", "TwoHand_Right", "Reset_PB"}
    assert {signal.name for signal in plan.outputs} >= {"Machine_Enable", "Trip_Lamp", "Alarm_Horn"}


def test_sequential_batch_requirement_returns_batch_plan() -> None:
    plan = PlanningAgent().generate_plan(
        project_id="PRJ-BATCH",
        requirement_text="Sequential batch reactor fill heat mix and drain process.",
        domain="Sequential Batch",
    )

    assert {signal.name for signal in plan.inputs} >= {"Start_Batch", "Level_OK", "Temp_PV", "Step_Timer"}
    assert {signal.name for signal in plan.outputs} >= {"Fill_Valve", "Heater", "Agitator", "Drain_Valve", "Batch_Complete"}


def test_unsupported_domain_returns_generic_valid_plan() -> None:
    plan = PlanningAgent().generate_plan(
        project_id="PRJ-GENERIC",
        requirement_text="Coordinate a generic industrial process enable with manual reset.",
        domain="Packaging",
    )

    assert plan.inputs
    assert plan.outputs
    assert plan.scope.standard == "IEC 61131-3"
    assert plan.scope.language == "Structured Text"
    assert {signal.name for signal in plan.inputs} >= {"Start_Cmd", "Stop_Cmd", "Reset_Cmd"}


def test_blank_requirement_is_rejected() -> None:
    with pytest.raises(ValueError, match="Requirement text must not be empty"):
        PlanningAgent().generate_plan(
            project_id="PRJ-BLANK",
            requirement_text="   ",
            domain="Motor Control",
        )


def test_llm_mode_is_placeholder_only() -> None:
    with pytest.raises(NotImplementedError, match="reserved for future integration"):
        PlanningAgent(mode="llm").generate_plan(
            project_id="PRJ-LLM",
            requirement_text="Motor start stop.",
            domain="Motor Control",
        )


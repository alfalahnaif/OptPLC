"""Behavior of the rule-based templates across scan cycles (P1-22, C-10, C-11, C-13, D-031).

Each test drives the generated program with the scan interpreter in app/tests/support. The inputs
of every scan are given in full, so a held button is always explicit.
"""

from app.agents import CodeGenerationAgent, PlanningAgent
from app.schemas.contracts import PlanObject, PlanScope, PlanSignal
from app.services.benchmark_runner import BenchmarkRunner
from app.services.st_syntax_check import ParserCheck
from app.tests.support.scan_sim import ScanSim

MOTOR_TEXT = "Motor start stop with emergency stop and overload protection and reset pushbutton."
BATCH_TEXT = "Sequential batch reactor fill heat mix and drain, then mark batch complete."
INTERLOCK_TEXT = "Safety interlock with guard switch two-hand control and reset."


async def _source(domain: str, text: str, project_id: str = "PRJ-T") -> str:
    plan = await PlanningAgent(mode="rule_based").generate_plan(project_id=project_id, requirement_text=text, domain=domain)
    return (await CodeGenerationAgent(mode="template_based").generate_code(project_id=project_id, plan=plan)).source


# --- Motor (C-10) --------------------------------------------------------------------------------

MOTOR_OK = {"Start_PB": False, "Stop_PB": True, "Emergency_Stop": True, "Overload": False, "Reset_PB": False}


def _motor_run(sim: ScanSim, **changes) -> bool:
    return sim.scan(**{**MOTOR_OK, **changes})["Motor_Run"]


async def test_motor_starts_on_a_press_and_seals_in() -> None:
    sim = ScanSim(await _source("Motor Control", MOTOR_TEXT))
    assert _motor_run(sim) is False
    assert _motor_run(sim, Start_PB=True) is True
    assert _motor_run(sim) is True


async def test_normally_closed_stop_drops_the_motor() -> None:
    sim = ScanSim(await _source("Motor Control", MOTOR_TEXT))
    _motor_run(sim, Start_PB=True)
    assert _motor_run(sim, Stop_PB=False) is False
    assert _motor_run(sim) is False


async def test_broken_stop_wire_prevents_a_start() -> None:
    sim = ScanSim(await _source("Motor Control", MOTOR_TEXT))
    _motor_run(sim, Stop_PB=False)
    assert _motor_run(sim, Start_PB=True, Stop_PB=False) is False


async def test_a_held_start_does_not_restart_after_stop_is_released() -> None:
    sim = ScanSim(await _source("Motor Control", MOTOR_TEXT))
    _motor_run(sim, Start_PB=True, Stop_PB=False)
    assert _motor_run(sim, Start_PB=True) is False


async def test_emergency_stop_latches_a_fault_that_needs_a_reset() -> None:
    sim = ScanSim(await _source("Motor Control", MOTOR_TEXT))
    _motor_run(sim, Start_PB=True)
    assert _motor_run(sim, Emergency_Stop=False) is False
    assert _motor_run(sim) is False
    assert _motor_run(sim, Start_PB=True) is False
    assert sim.peek("Fault_State") is True
    _motor_run(sim, Reset_PB=True)
    assert sim.peek("Fault_State") is False
    assert _motor_run(sim, Start_PB=True) is True


async def test_a_reset_never_starts_the_motor() -> None:
    sim = ScanSim(await _source("Motor Control", MOTOR_TEXT))
    _motor_run(sim, Overload=True)
    _motor_run(sim)
    _motor_run(sim, Start_PB=True)
    assert _motor_run(sim, Start_PB=True, Reset_PB=True) is False
    assert _motor_run(sim, Start_PB=True) is False
    _motor_run(sim, Overload=True)
    _motor_run(sim)
    assert _motor_run(sim, Start_PB=True, Reset_PB=True) is False
    assert _motor_run(sim, Start_PB=True) is False


async def test_motor_without_reset_input_needs_a_new_start_after_emergency_stop() -> None:
    sim = ScanSim(await _source("Motor Control", "Motor start stop with emergency stop."))
    ok = {"Start_PB": False, "Stop_PB": True, "Emergency_Stop": True}
    assert sim.scan(**{**ok, "Start_PB": True})["Motor_Run"] is True
    assert sim.scan(**{**ok, "Emergency_Stop": False})["Motor_Run"] is False
    assert sim.scan(**ok)["Motor_Run"] is False
    assert sim.scan(**{**ok, "Start_PB": True})["Motor_Run"] is True


# --- Batch (C-11) --------------------------------------------------------------------------------

BATCH_OK = {
    "Start_PB": False,
    "Emergency_Stop": True,
    "Abort_PB": False,
    "Reset_PB": False,
    "High_Level": False,
    "Low_Level": False,
    "Mix_Timer_Done": False,
}


def _batch(sim: ScanSim, **changes) -> dict:
    return sim.scan(**{**BATCH_OK, **changes})


async def _run_one_batch(sim: ScanSim) -> list[dict]:
    return [
        _batch(sim, Start_PB=True),
        _batch(sim),
        _batch(sim, High_Level=True),
        _batch(sim, Mix_Timer_Done=True),
        _batch(sim),
        _batch(sim, Low_Level=True),
    ]


async def test_batch_runs_fill_mix_drain_and_holds_complete() -> None:
    sim = ScanSim(await _source("Sequential Batch", BATCH_TEXT))
    scans = await _run_one_batch(sim)
    assert scans[0]["Fill_Valve"] is True
    assert scans[2]["Mixer_Motor"] is True
    assert scans[3]["Drain_Valve"] is True
    assert scans[5]["Batch_Complete"] is True
    assert _batch(sim)["Batch_Complete"] is True
    assert _batch(sim)["Batch_Complete"] is True


async def test_a_new_start_clears_complete_and_refills() -> None:
    sim = ScanSim(await _source("Sequential Batch", BATCH_TEXT))
    await _run_one_batch(sim)
    outputs = _batch(sim, Start_PB=True)
    assert outputs["Batch_Complete"] is False
    assert outputs["Fill_Valve"] is True


async def test_abort_forces_outputs_off_and_latches_a_fault() -> None:
    sim = ScanSim(await _source("Sequential Batch", BATCH_TEXT))
    _batch(sim, Start_PB=True)
    outputs = _batch(sim, Abort_PB=True)
    assert not any(outputs.values())
    assert _batch(sim, Start_PB=True)["Fill_Valve"] is False
    _batch(sim, Reset_PB=True)
    assert _batch(sim, Start_PB=True)["Fill_Valve"] is True


async def test_fill_and_drain_are_never_open_together() -> None:
    sim = ScanSim(await _source("Sequential Batch", BATCH_TEXT))
    for outputs in await _run_one_batch(sim):
        assert not (outputs["Fill_Valve"] and outputs["Drain_Valve"])


# --- Safety interlock (C-13 routing, power-up reset, two-hand synchronism) -----------------------

HANDS_OFF = {"Guard_Closed": True, "Fault_Input": False, "Reset_PB": False, "TwoHand_Left": False, "TwoHand_Right": False}
BOTH = {"TwoHand_Left": True, "TwoHand_Right": True}


def _enable(sim: ScanSim, **changes) -> bool:
    return sim.scan(**{**HANDS_OFF, **changes})["Machine_Enable"]


async def _armed_interlock() -> ScanSim:
    sim = ScanSim(await _source("Safety Interlocks", INTERLOCK_TEXT))
    _enable(sim)
    _enable(sim, Reset_PB=True)
    return sim


async def test_interlock_needs_a_reset_after_power_up() -> None:
    sim = ScanSim(await _source("Safety Interlocks", INTERLOCK_TEXT))
    assert _enable(sim, **BOTH) is False
    assert sim.scan(**HANDS_OFF)["Trip_Lamp"] is True


async def test_both_hands_together_enable_the_machine() -> None:
    sim = await _armed_interlock()
    assert _enable(sim, **BOTH) is True
    assert _enable(sim) is False


async def test_a_second_hand_later_than_half_a_second_is_rejected() -> None:
    sim = await _armed_interlock()
    for _ in range(6):
        _enable(sim, TwoHand_Left=True)
    assert _enable(sim, **BOTH) is False
    _enable(sim)
    _enable(sim, TwoHand_Left=True)
    assert _enable(sim, **BOTH) is True


async def test_releasing_one_hand_requires_releasing_both() -> None:
    sim = await _armed_interlock()
    _enable(sim, **BOTH)
    assert _enable(sim, TwoHand_Left=True) is False
    assert _enable(sim, **BOTH) is False
    _enable(sim)
    assert _enable(sim, **BOTH) is True


async def test_releasing_both_hands_at_once_rearms_immediately() -> None:
    """Found in P1-22: a full release right after activation used to leave the control disarmed."""
    sim = await _armed_interlock()
    assert _enable(sim, **BOTH) is True
    assert _enable(sim) is False
    assert _enable(sim, **BOTH) is True


async def test_opening_the_guard_trips_and_latches() -> None:
    sim = await _armed_interlock()
    _enable(sim, **BOTH)
    assert _enable(sim, **BOTH, Guard_Closed=False) is False
    assert _enable(sim, **BOTH) is False
    _enable(sim, Reset_PB=True)
    assert _enable(sim, **BOTH) is True


async def test_singular_safety_interlock_domain_gets_the_interlock_template() -> None:
    """C-13: "Safety Interlock" used to fall through to the generic template with undeclared signals."""
    source = await _source("Safety Interlock", INTERLOCK_TEXT)
    assert "Machine_Enable :=" in source
    assert ParserCheck().check(source) == []


# --- Routing guard ---------------------------------------------------------------------------------


async def test_every_benchmark_template_uses_only_declared_signals() -> None:
    for case in BenchmarkRunner().list_cases():
        source = await _source(case.domain, case.requirement, f"PRJ-{case.id}")
        assert ParserCheck().check(source) == [], case.id


async def test_a_plan_without_a_matching_template_holds_its_outputs_safe() -> None:
    plan = PlanObject(
        projectId="PRJ-CUSTOM",
        domain="Motor Control",
        agent="test",
        generatedAt="2026-09-15T00:00:00Z",
        inputs=[PlanSignal(name="Jog_Button", type="BOOL", source="DI-01", description="Jog")],
        outputs=[PlanSignal(name="Winch_Up", type="BOOL", address="DO-01", description="Winch")],
        logicRules=[],
        safetyConstraints=[],
        scope=PlanScope(standard="IEC 61131-3", edition="3rd", language="Structured Text", runtime="any"),
    )
    source = (await CodeGenerationAgent(mode="template_based").generate_code(project_id="PRJ-CUSTOM", plan=plan)).source
    assert ParserCheck().check(source) == []
    assert ScanSim(source).scan(Jog_Button=True) == {"Winch_Up": False}

"""Semantic MC-2 check (P1-22, D-031): a start branch must be guarded by stop, safety, or fault logic.

The text-pattern version of MC-2 accepted a motor template that can never run and rejected the
correct stop-dominant latch (C-14). These cases pin the parse-tree check in both directions.
"""

from app.agents import CodeGenerationAgent, PlanningAgent, ValidationAgent
from app.services.st_rules import start_paths_guarded

HEAD = (
    "PROGRAM P\nVAR_INPUT\n    Start_PB : BOOL;\n    Stop_PB : BOOL;\n    Fault_Lamp : BOOL;\nEND_VAR\n"
    "VAR_OUTPUT\n    Run_Cmd : BOOL;\n    Ready : BOOL;\nEND_VAR\n"
)


def program(body: str) -> str:
    return f"{HEAD}{body}\nEND_PROGRAM"


def test_stop_dominant_latch_is_guarded() -> None:
    source = program("IF NOT Stop_PB THEN\n    Run_Cmd := FALSE;\nELSIF Start_PB THEN\n    Run_Cmd := TRUE;\nEND_IF;")
    assert start_paths_guarded(source) is True


def test_a_guard_inside_the_start_condition_counts() -> None:
    assert start_paths_guarded(program("IF Start_PB AND Stop_PB THEN\n    Run_Cmd := TRUE;\nEND_IF;")) is True


def test_an_unguarded_start_is_rejected() -> None:
    source = program("IF Start_PB THEN\n    Run_Cmd := TRUE;\nEND_IF;\nIF NOT Stop_PB THEN\n    Run_Cmd := FALSE;\nEND_IF;")
    assert start_paths_guarded(source) is False


def test_a_guard_branch_that_clears_another_variable_does_not_count() -> None:
    source = program("IF Fault_Lamp THEN\n    Ready := FALSE;\nELSIF Start_PB THEN\n    Run_Cmd := TRUE;\nEND_IF;")
    assert start_paths_guarded(source) is False


def test_no_start_branch_or_unparseable_source_gives_no_verdict() -> None:
    assert start_paths_guarded(program("Run_Cmd := Stop_PB;")) is None
    assert start_paths_guarded("PROGRAM broken") is None


async def test_the_correct_motor_template_passes_and_a_start_dominant_variant_fails_mc2() -> None:
    plan = await PlanningAgent(mode="rule_based").generate_plan(
        project_id="PRJ-MC2",
        requirement_text="Motor start stop with emergency stop and overload protection.",
        domain="Motor Control",
    )
    artifact = await CodeGenerationAgent(mode="template_based").generate_code(project_id="PRJ-MC2", plan=plan)
    agent = ValidationAgent()

    assert agent.validate(project_id="PRJ-MC2", artifact=artifact, plan=plan).status == "CHECKS_PASSED"

    # Start wins over Stop when both happen in one scan: unsafe, and MC-2 must say so.
    start_dominant = artifact.source.replace("ELSIF Start_Edge.Q THEN", "END_IF;\nIF Start_Edge.Q THEN")
    report = agent.validate(project_id="PRJ-MC2", artifact=artifact.model_copy(update={"source": start_dominant}), plan=plan)
    assert any(result.id == "MC-2" and result.status == "failed" for result in report.safetyResults)

"""Parser check that replaces the regex fallback when MATIEC is unavailable (P1-01, C-01, D-029)."""

import pytest

from app.agents import CodeGenerationAgent, PlanningAgent
from app.services.benchmark_runner import BenchmarkRunner
from app.services.st_syntax_check import ParserCheck, strip_comments_and_strings

CHECK = ParserCheck()


def program(declarations: str, body: str) -> str:
    return f"PROGRAM P\n{declarations}\n{body}\nEND_PROGRAM"


MINIMAL = program("VAR\n    X : BOOL;\nEND_VAR", "X := TRUE;")


def test_minimal_program_passes() -> None:
    assert CHECK.check(MINIMAL) == []


def test_every_var_block_kind_and_qualifier_passes() -> None:
    source = program(
        "VAR_INPUT\n    A : BOOL;\nEND_VAR\n"
        "VAR_OUTPUT\n    B : BOOL;\nEND_VAR\n"
        "VAR_IN_OUT\n    C : INT;\nEND_VAR\n"
        "VAR_TEMP\n    D : INT;\nEND_VAR\n"
        "VAR CONSTANT\n    K : INT := 3;\nEND_VAR\n"
        "VAR RETAIN\n    R : DINT;\nEND_VAR\n"
        "VAR\n    E : BOOL;\nEND_VAR",
        "B := A AND E;\nC := C + K;\nD := C;\nR := D;",
    )
    assert CHECK.check(source) == []


def test_keywords_inside_comments_and_strings_are_ignored() -> None:
    source = program(
        "VAR\n    X : BOOL;\n    S : STRING;\nEND_VAR",
        "(* IF VAR END_IF PROGRAM CASE *)\n// VAR_INPUT FOR WHILE\nS := 'IF END_VAR';\nX := TRUE;",
    )
    assert strip_comments_and_strings(source).count("\n") == source.count("\n")
    assert CHECK.check(source) == []


def test_missing_end_program_is_reported() -> None:
    assert CHECK.check(MINIMAL.replace("END_PROGRAM", "")) == ["Missing END_PROGRAM"]


def test_missing_program_declaration_is_reported() -> None:
    errors = CHECK.check("VAR\n    X : BOOL;\nEND_VAR\nX := TRUE;")
    assert "Missing PROGRAM or FUNCTION_BLOCK declaration" in errors


def test_unclosed_var_block_is_reported() -> None:
    errors = CHECK.check(program("VAR_INPUT\n    A : BOOL;\nVAR\n    X : BOOL;\nEND_VAR", "X := A;"))
    assert any("VAR_INPUT" in error and "END_VAR" in error for error in errors)


def test_unclosed_if_is_reported() -> None:
    errors = CHECK.check(program("VAR\n    X : BOOL;\nEND_VAR", "IF X THEN\n    X := FALSE;"))
    assert errors == ["Unbalanced IF statements: 1 IF vs 0 END_IF"]


def test_equals_instead_of_assignment_is_rejected_with_position() -> None:
    errors = CHECK.check(program("VAR\n    X : BOOL;\nEND_VAR", "X = TRUE;"))
    assert len(errors) == 1
    assert "line 5" in errors[0]


def test_undeclared_assigned_variable_is_reported() -> None:
    errors = CHECK.check(program("VAR\n    X : BOOL;\nEND_VAR", "Ghost_Output := X;"))
    assert errors == ["Variable 'Ghost_Output' is not declared in any VAR block (line 5)."]


def test_undeclared_read_is_reported_once() -> None:
    errors = CHECK.check(program("VAR\n    X : BOOL;\nEND_VAR", "X := Ghost;\nX := Ghost AND X;"))
    assert errors == ["Variable 'Ghost' is not declared in any VAR block (line 5)."]


def test_identifiers_are_case_insensitive() -> None:
    assert CHECK.check(program("VAR\n    Motor_Run : BOOL;\nEND_VAR", "MOTOR_RUN := TRUE;")) == []


def test_function_block_instances_and_members_pass() -> None:
    source = program(
        "VAR\n    Start : BOOL;\n    Delay : TON;\n    Edge : R_TRIG;\n    Count : CTU;\n    Done : BOOL;\nEND_VAR",
        "Delay(IN := Start, PT := T#2s);\nEdge(CLK := Start);\nCount(CU := Edge.Q, PV := 10);\nDone := Delay.Q AND Count.Q;",
    )
    assert CHECK.check(source) == []


def test_standard_functions_and_conversions_pass() -> None:
    source = program(
        "VAR\n    A : INT;\n    B : INT;\n    R : REAL;\nEND_VAR",
        "A := MAX(A, B);\nB := LIMIT(0, A, 100);\nR := INT_TO_REAL(A);",
    )
    assert CHECK.check(source) == []


def test_unknown_call_is_reported() -> None:
    errors = CHECK.check(program("VAR\n    X : BOOL;\nEND_VAR", "X := Foo(X);"))
    assert errors == ["Called name 'Foo' is not declared and is not an IEC 61131-3 standard function (line 5)."]


@pytest.mark.parametrize(
    ("declarations", "body"),
    [
        ("VAR\n    A : BOOL;\n    N : INT;\nEND_VAR", "A := A XOR TRUE;\nN := N MOD 2;\nA := A & TRUE;\nN := N ** 2;"),
        ("VAR\n    N : INT;\nEND_VAR", "REPEAT\n    N := N + 1;\nUNTIL N > 3\nEND_REPEAT;"),
        (
            "VAR\n    N : INT;\nEND_VAR",
            "WHILE TRUE DO\n    N := N + 1;\n    IF N > 3 THEN\n        EXIT;\n    END_IF;\nEND_WHILE;\nRETURN;",
        ),
        ("VAR\n    N : INT;\n    W : WORD;\n    B : BOOL;\nEND_VAR", "N := INT#5;\nW := 16#FF;\nB := BOOL#TRUE;\nN := 2#1010;"),
        (
            "VAR\n    A : ARRAY[0..3] OF INT := [1, 2, 3, 4];\n    M : ARRAY[1..2, 1..2] OF BOOL;\nEND_VAR",
            "A[0] := A[1] + 1;\nM[1, 2] := TRUE;",
        ),
    ],
    ids=["xor-mod-amp-power", "repeat-until", "exit-return", "typed-and-based-literals", "arrays"],
)
def test_widened_grammar_constructs_pass(declarations: str, body: str) -> None:
    assert CHECK.check(program(declarations, body)) == []


def test_empty_source_is_reported() -> None:
    assert CHECK.check("   ") == ["CodeArtifact source is empty."]


async def _template_source(case_id: str) -> str:
    case = next(case for case in BenchmarkRunner().list_cases() if case.id == case_id)
    plan = await PlanningAgent(mode="rule_based").generate_plan(
        project_id=f"PRJ-{case.id}", requirement_text=case.requirement, domain=case.domain
    )
    artifact = await CodeGenerationAgent(mode="template_based").generate_code(project_id=f"PRJ-{case.id}", plan=plan)
    return artifact.source


@pytest.mark.parametrize("case_id", ["B001", "B002", "B003", "B004", "B005"])
async def test_benchmark_templates_pass(case_id: str) -> None:
    """B004 was rejected for undeclared signals until P1-22 fixed its routing (C-13)."""
    assert CHECK.check(await _template_source(case_id)) == []


def test_step_is_a_reserved_name() -> None:
    """P1-03, D-006: MATIEC rejects a variable named Step (STEP is an SFC keyword)."""
    errors = CHECK.check(program("VAR\n    Step : INT;\nEND_VAR", "Step := 1;"))
    assert errors == ["Variable name 'Step' is a reserved IEC 61131-3 keyword (SFC); MATIEC rejects it (line 3)."]


def test_named_constant_case_labels_are_rejected() -> None:
    """P1-03, D-006: MATIEC accepts only literal CASE labels."""
    errors = CHECK.check(
        program(
            "VAR CONSTANT\n    IDLE : INT := 0;\nEND_VAR\nVAR\n    Phase : INT;\n    X : BOOL;\nEND_VAR",
            "CASE Phase OF\n    IDLE: X := FALSE;\nEND_CASE;",
        )
    )
    assert errors == ["CASE label 'IDLE' is a named constant; MATIEC accepts only literal labels (line 10)."]

import logging

from app.services.metrics_service import MetricsService


def test_if_increases_cyclomatic_complexity() -> None:
    metrics = MetricsService.calculate(
        """
PROGRAM P
VAR_INPUT
    A : BOOL;
END_VAR
VAR_OUTPUT
    B : BOOL;
END_VAR
IF A THEN
    B := TRUE;
END_IF;
END_PROGRAM
"""
    )
    assert metrics.cyclomaticComplexity == 2


def test_elsif_increases_cyclomatic_complexity() -> None:
    metrics = MetricsService.calculate(
        """
PROGRAM P
VAR_INPUT
    A : BOOL;
    C : BOOL;
END_VAR
VAR_OUTPUT
    B : BOOL;
END_VAR
IF A THEN
    B := TRUE;
ELSIF C THEN
    B := FALSE;
END_IF;
END_PROGRAM
"""
    )
    assert metrics.cyclomaticComplexity == 3


def test_case_branches_increase_cyclomatic_complexity() -> None:
    metrics = MetricsService.calculate(
        """
PROGRAM P
VAR_INPUT
    S : INT;
END_VAR
VAR_OUTPUT
    B : BOOL;
END_VAR
CASE S OF
    1: B := TRUE;
    2: B := FALSE;
END_CASE;
END_PROGRAM
"""
    )
    assert metrics.cyclomaticComplexity == 3


def test_comments_do_not_increase_cyclomatic_complexity() -> None:
    metrics = MetricsService.calculate(
        """
PROGRAM P
VAR_INPUT
    A : BOOL;
END_VAR
VAR_OUTPUT
    B : BOOL;
END_VAR
(* IF fake THEN *)
// ELSIF fake THEN
B := A;
END_PROGRAM
"""
    )
    assert metrics.cyclomaticComplexity == 1


def test_invalid_st_falls_back_without_crashing(caplog) -> None:
    with caplog.at_level(logging.INFO):
        metrics = MetricsService.calculate("IF A THEN B := TRUE;")
    assert isinstance(metrics.cyclomaticComplexity, int)
    assert metrics.cyclomaticComplexity >= 1
    assert "fallback used" in caplog.text.lower()


def test_loc_ignores_comments_and_structural_lines() -> None:
    metrics = MetricsService.calculate(
        """
PROGRAM P
VAR_INPUT
    A : BOOL;
END_VAR
VAR_OUTPUT
    B : BOOL;
END_VAR
(* comment line *)
// comment line

B := A;
END_PROGRAM
"""
    )
    assert metrics.loc == 1


def test_ton_contributes_to_estimated_scan_time() -> None:
    no_timer = MetricsService.calculate(
        """
PROGRAM P
VAR_INPUT
    A : BOOL;
END_VAR
VAR_OUTPUT
    B : BOOL;
END_VAR
B := A;
END_PROGRAM
"""
    )
    with_timer = MetricsService.calculate(
        """
PROGRAM P
VAR_INPUT
    A : BOOL;
END_VAR
VAR_OUTPUT
    B : BOOL;
END_VAR
VAR
    T1 : TON;
END_VAR
T1(IN := A, PT := T#2S);
B := A;
END_PROGRAM
"""
    )
    assert with_timer.estimatedScanTimeMs > no_timer.estimatedScanTimeMs

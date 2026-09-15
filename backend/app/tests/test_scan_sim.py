"""The scan-cycle interpreter used by the template behavior tests must itself be right (P1-22, D-031)."""

import pytest

from app.tests.support.scan_sim import ScanSim

LATCH = """PROGRAM Latch
VAR_INPUT
    Set_In : BOOL;
    Reset_In : BOOL;
END_VAR
VAR_OUTPUT
    Q : BOOL;
END_VAR
IF Reset_In THEN
    Q := FALSE;
ELSIF Set_In THEN
    Q := TRUE;
END_IF;
END_PROGRAM"""


def test_latch_sets_holds_and_resets_across_scans() -> None:
    sim = ScanSim(LATCH)
    assert sim.scan(Set_In=False, Reset_In=False) == {"Q": False}
    assert sim.scan(Set_In=True) == {"Q": True}
    assert sim.scan(Set_In=False) == {"Q": True}
    assert sim.scan(Reset_In=True) == {"Q": False}


def test_case_uses_integer_labels_and_else() -> None:
    sim = ScanSim(
        "PROGRAM P\nVAR_INPUT\n    Mode : INT;\nEND_VAR\nVAR_OUTPUT\n    Out : INT;\nEND_VAR\n"
        "CASE Mode OF\n    1: Out := 10;\n    2, 3: Out := 20;\nELSE\n    Out := -1;\nEND_CASE;\nEND_PROGRAM"
    )
    assert sim.scan(Mode=1) == {"Out": 10}
    assert sim.scan(Mode=3) == {"Out": 20}
    assert sim.scan(Mode=7) == {"Out": -1}


def test_r_trig_gives_a_one_scan_pulse() -> None:
    sim = ScanSim(
        "PROGRAM P\nVAR_INPUT\n    Button : BOOL;\nEND_VAR\nVAR_OUTPUT\n    Pulse : BOOL;\nEND_VAR\n"
        "VAR\n    Edge : R_TRIG;\nEND_VAR\nEdge(CLK := Button);\nPulse := Edge.Q;\nEND_PROGRAM"
    )
    assert [sim.scan(Button=b)["Pulse"] for b in (False, True, True, False, True)] == [False, True, False, False, True]


def test_ton_needs_the_full_preset_and_resets_when_input_drops() -> None:
    sim = ScanSim(
        "PROGRAM P\nVAR_INPUT\n    Run : BOOL;\nEND_VAR\nVAR_OUTPUT\n    Done : BOOL;\nEND_VAR\n"
        "VAR\n    Delay : TON;\nEND_VAR\nDelay(IN := Run, PT := T#300ms);\nDone := Delay.Q;\nEND_PROGRAM",
        dt_ms=100,
    )
    assert [sim.scan(Run=True)["Done"] for _ in range(3)] == [False, False, True]
    assert sim.scan(Run=False)["Done"] is False
    assert sim.scan(Run=True)["Done"] is False


def test_initializers_are_applied() -> None:
    sim = ScanSim("PROGRAM P\nVAR_OUTPUT\n    Q : BOOL;\nEND_VAR\nVAR\n    Armed : BOOL := TRUE;\nEND_VAR\nQ := Armed;\nEND_PROGRAM")
    assert sim.scan() == {"Q": True}


def test_unknown_input_names_are_rejected() -> None:
    with pytest.raises(KeyError):
        ScanSim(LATCH).scan(Sett_In=True)

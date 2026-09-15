"""MATIEC compile path (P1-02, D-005, D-030).

The delivered source must reach iec2c exactly as written, each compile must use its own
temporary directory, and every failure mode must fail closed or report MATIEC as unavailable.
These tests replace subprocess.run, so they never need a local iec2c binary.
"""

import subprocess
from pathlib import Path

import pytest

from app.config import settings
from app.services import validation_service
from app.services.validation_service import MatiecValidator

TIMER_PROGRAM = """PROGRAM Timer_Demo
VAR_INPUT
    Start : BOOL;
END_VAR
VAR_OUTPUT
    Lamp : BOOL;
END_VAR
VAR
    Delay : TON;
END_VAR
Delay(IN := Start, PT := T#5s);
Lamp := Delay.Q;
END_PROGRAM
"""


@pytest.fixture
def fake_matiec(tmp_path, monkeypatch):
    """Points settings at a fake iec2c and library and records every compile."""
    binary = tmp_path / "iec2c"
    binary.write_text("")
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "ieclib.txt").write_text("")
    monkeypatch.setattr(settings, "matiec_bin", str(binary))
    monkeypatch.setattr(settings, "matiec_lib_dir", str(lib))

    state = {"calls": [], "returncode": 0, "stdout": "", "stderr": "", "timeout": False}

    def fake_run(command, **kwargs):
        source_path = Path(command[-1])
        output_dir = Path(command[command.index("-T") + 1])
        state["calls"].append(
            {
                "command": command,
                "cwd": Path(kwargs["cwd"]),
                "source": source_path.read_text(encoding="utf-8"),
                "output_dir_existed": output_dir.is_dir(),
                "work_dir": source_path.parent,
            }
        )
        if state["timeout"]:
            raise subprocess.TimeoutExpired(command, kwargs.get("timeout"))
        return subprocess.CompletedProcess(command, state["returncode"], state["stdout"], state["stderr"])

    monkeypatch.setattr(validation_service.subprocess, "run", fake_run)
    state["binary"] = binary
    state["lib"] = lib
    return state


def test_source_reaches_iec2c_exactly_as_written(fake_matiec) -> None:
    result = MatiecValidator().validate_syntax_sync(TIMER_PROGRAM)

    assert result["passed"] is True
    assert result["method"] == "matiec"
    assert fake_matiec["calls"][0]["source"] == TIMER_PROGRAM


def test_command_uses_the_library_and_a_private_output_dir(fake_matiec) -> None:
    MatiecValidator().validate_syntax_sync(TIMER_PROGRAM)

    call = fake_matiec["calls"][0]
    work_dir = call["work_dir"]
    assert call["command"] == [
        str(fake_matiec["binary"]),
        "-f",
        "-I",
        str(fake_matiec["lib"]),
        "-T",
        str(work_dir / "out"),
        str(work_dir / "input.st"),
    ]
    assert call["cwd"] == work_dir
    assert call["output_dir_existed"] is True
    assert not work_dir.exists()


def test_each_compile_gets_its_own_directory(fake_matiec) -> None:
    validator = MatiecValidator()
    validator.validate_syntax_sync(TIMER_PROGRAM)
    validator.validate_syntax_sync(TIMER_PROGRAM)

    first, second = fake_matiec["calls"]
    assert first["work_dir"] != second["work_dir"]


def test_compiler_diagnostics_fail_the_check(fake_matiec) -> None:
    fake_matiec["returncode"] = 1
    fake_matiec["stderr"] = "input.st:8: error: invalid variable before ':=' in ST assignment statement."

    result = MatiecValidator().validate_syntax_sync(TIMER_PROGRAM)

    assert result["passed"] is False
    assert result["errors"] == ["input.st:8: error: invalid variable before ':=' in ST assignment statement."]
    assert result["return_code"] == 1


def test_nonzero_exit_without_diagnostics_still_fails(fake_matiec) -> None:
    fake_matiec["returncode"] = 2

    result = MatiecValidator().validate_syntax_sync(TIMER_PROGRAM)

    assert result["passed"] is False
    assert result["errors"] == ["MATIEC exited with return code 2."]


def test_timeout_fails_closed(fake_matiec) -> None:
    fake_matiec["timeout"] = True

    result = MatiecValidator().validate_syntax_sync(TIMER_PROGRAM)

    assert result["passed"] is False
    assert "timed out" in result["errors"][0]


def test_missing_binary_is_reported_as_unavailable(fake_matiec, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "matiec_bin", str(tmp_path / "missing" / "iec2c"))

    result = MatiecValidator().validate_syntax_sync(TIMER_PROGRAM)

    assert result["method"] == "unavailable"
    assert result["passed"] is None
    assert "missing" in result["reason"]
    assert fake_matiec["calls"] == []


def test_missing_library_is_reported_as_unavailable(fake_matiec, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "matiec_lib_dir", str(tmp_path / "no-lib"))

    result = MatiecValidator().validate_syntax_sync(TIMER_PROGRAM)

    assert result["method"] == "unavailable"
    assert "library" in result["reason"]
    assert fake_matiec["calls"] == []


def test_empty_source_fails_without_compiling(fake_matiec) -> None:
    result = MatiecValidator().validate_syntax_sync("   ")

    assert result["passed"] is False
    assert fake_matiec["calls"] == []


async def test_async_entry_point_runs_the_same_compile(fake_matiec) -> None:
    result = await MatiecValidator().validate_syntax(TIMER_PROGRAM)

    assert result["passed"] is True
    assert fake_matiec["calls"][0]["source"] == TIMER_PROGRAM


def test_the_normalizer_is_gone() -> None:
    """D-005: normalization hid real errors, so it must not come back."""
    assert not hasattr(MatiecValidator, "_normalize_for_matiec")
    assert not hasattr(MatiecValidator, "_collapse_multiline_assignments")

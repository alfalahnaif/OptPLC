import json
from hashlib import sha256
from pathlib import Path

import pytest

from research.core.nuxmv_witness import (
    WitnessParseError,
    parse_nuxmv_output,
    read_nuxmv_output,
    write_witnesses_json,
)


FIXTURES = Path(__file__).parent / "fixtures"
PROPERTY_IDS = {
    "G (!E_Stop -> !Machine_Enable_After_Scan)": "P-I2",
    "G (Fault_Latched -> !Machine_Enable_After_Scan)": "P-I5",
}
ROLES = {
    "E_Stop": "input",
    "Machine_Enable_After_Scan": "output",
    "Fault_Latched": "state",
    "Step_State": "state",
}


def parse_fixture(name="mixed_g3.txt"):
    source = FIXTURES / name
    return parse_nuxmv_output(
        source.read_text(encoding="utf-8"),
        case_id="E27-I01",
        mutant_id="I-M4",
        property_ids=PROPERTY_IDS,
        variable_roles=ROLES,
        source_output_path=str(source),
    )


def test_sparse_lasso_trace_and_passing_property():
    failed, passed = parse_fixture()
    assert failed.verification_status == "VIOLATED"
    assert failed.property_id == "P-I2"
    assert failed.tool == "nuXmv"
    assert failed.tool_version == "2.2.0"
    assert len(failed.steps) == 3
    assert failed.steps[1].inputs == {"E_Stop": False}
    assert failed.steps[1].outputs == {"Machine_Enable_After_Scan": True}
    assert failed.steps[1].state == {"Fault_Latched": False, "Step_State": "0"}
    assert failed.steps[1].changed_variables == ["E_Stop", "Machine_Enable_After_Scan"]
    assert failed.steps[1].carried_variables == ["Fault_Latched", "Step_State"]
    assert failed.steps[2].changed_variables == []
    assert failed.steps[2].loop_start is True
    assert failed.transitions[-1].loop_back is True
    assert failed.transitions[-1].to_index == 2
    assert passed.verification_status == "SATISFIED"
    assert passed.steps == []
    assert failed.raw_source.startswith("*** This is nuXmv")


def test_json_writer_preserves_raw_source(tmp_path):
    witnesses = parse_fixture()
    output = tmp_path / "witnesses.json"
    write_witnesses_json(witnesses, output)
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved[0]["raw_source"] == witnesses[0].raw_source
    assert saved[0]["steps"][2]["loop_start"] is True
    assert saved[1]["steps"] == []


def test_malformed_assignment_fails_explicitly():
    with pytest.raises(WitnessParseError, match="assignment"):
        parse_fixture("malformed_g3.txt")


def test_missing_property_mapping_fails_explicitly():
    with pytest.raises(WitnessParseError, match="property ID"):
        parse_nuxmv_output(
            (FIXTURES / "mixed_g3.txt").read_text(encoding="utf-8"),
            case_id="E27-I01",
            mutant_id="I-M4",
            property_ids={},
            variable_roles=ROLES,
            source_output_path="raw.txt",
        )


def test_missing_variable_role_fails_explicitly():
    with pytest.raises(WitnessParseError, match="roles missing"):
        parse_nuxmv_output(
            (FIXTURES / "mixed_g3.txt").read_text(encoding="utf-8"),
            case_id="E27-I01", mutant_id="I-M4", property_ids=PROPERTY_IDS,
            variable_roles={"E_Stop": "input"}, source_output_path="raw.txt",
        )


def test_unknown_initial_value_fails_instead_of_backfilling():
    raw = """-- specification G x is false
Trace Type: Counterexample
  -> State: 1.1 <-
    x = TRUE
  -> State: 1.2 <-
    y = FALSE
"""
    with pytest.raises(WitnessParseError, match="initial state"):
        parse_nuxmv_output(
            raw, case_id="C", mutant_id="M", property_ids={"G x": "P"},
            variable_roles={"x": "state", "y": "state"},
            source_output_path="raw.txt",
        )


@pytest.mark.parametrize("verdict,status", [("unknown", "UNKNOWN"), ("error", "ERROR")])
def test_explicit_nonboolean_verdict_has_no_trace(verdict, status):
    result = parse_nuxmv_output(
        f"-- specification G x is {verdict}\n",
        case_id="C", mutant_id="M", property_ids={"G x": "P"},
        variable_roles={}, source_output_path="raw.txt",
    )
    assert result[0].verification_status == status
    assert result[0].steps == []


def test_global_nuxmv_error_requires_explicit_run_property_id():
    raw = "file.smv: line 10: Error: unexpected token\n"
    result = parse_nuxmv_output(
        raw, case_id="C", mutant_id="M", property_ids={"__run__": "P"},
        variable_roles={}, source_output_path="raw.txt",
    )
    assert result[0].verification_status == "ERROR"
    assert result[0].steps == []
    assert result[0].raw_source == raw


def test_nonboolean_value_and_original_name_are_preserved():
    raw = """-- specification G x is false
Trace Type: Counterexample
  -> State: 1.1 <-
    main.array[0] = 0sd16_42
    x = TRUE
  -> State: 1.2 <-
    x = FALSE
"""
    result = parse_nuxmv_output(
        raw, case_id="C", mutant_id="M", property_ids={"G x": "P"},
        variable_roles={"main.array[0]": "state", "x": "input"},
        source_output_path="raw.txt",
    )[0]
    assert result.steps[1].state == {"main.array[0]": "0sd16_42"}
    assert result.steps[1].inputs == {"x": False}
    assert result.steps[1].carried_variables == ["main.array[0]"]


def test_utf16_pilot_encoding_retains_source_bytes_hash_and_line_endings(tmp_path):
    source = tmp_path / "pilot.txt"
    original = "*** This is nuXmv 2.2.0\r\n-- specification G x is true\r\n"
    source.write_bytes(original.encode("utf-16"))
    raw = read_nuxmv_output(source)
    assert raw.text == original
    assert raw.encoding == "utf-16"
    assert raw.sha256 == sha256(source.read_bytes()).hexdigest()
    witness = parse_nuxmv_output(
        raw.text, case_id="C", mutant_id="M", property_ids={"G x": "P"},
        variable_roles={}, source_output_path=str(source),
        source_encoding=raw.encoding, source_sha256=raw.sha256,
    )[0]
    assert witness.source_sha256 == raw.sha256
    assert witness.raw_source == original

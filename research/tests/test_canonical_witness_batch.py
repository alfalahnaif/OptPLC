import json
from hashlib import sha256
from pathlib import Path

import pytest

from research.core.extract_pilot_witnesses import ManifestError, extract_manifest


PROPERTY_IDS = {"G x": "P-X", "G y": "P-Y"}


def _log(*verdicts):
    parts = ["*** This is nuXmv 2.2.0"]
    for formula, status in verdicts:
        parts.append(f"-- specification {formula} is {status}")
        if status == "false":
            parts.extend(("Trace Type: Counterexample", "  -> State: 1.1 <-", "    x = TRUE"))
    return "\n".join(parts) + "\n"


def _setup(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    output = tmp_path / "witnesses"
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"set-1": {"property_ids": PROPERTY_IDS,
                                           "variable_roles": {"x": "input"}}}), encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    return results, output, config, manifest


def _entry(case, mutant, path, canonical=True, expected_hash=None):
    entry = {"case_id": case, "mutant_id": mutant, "log_path": path,
             "property_set": "set-1", "canonical": canonical}
    if expected_hash is not None:
        entry["expected_source_sha256"] = expected_hash
    return entry


def _run(results, output, config, manifest, entries):
    manifest.write_text(json.dumps({"schema_version": 1, "runs": entries}), encoding="utf-8")
    return extract_manifest(manifest, results, output, config)


def test_stale_log_is_preserved_but_excluded_from_index_and_summary(tmp_path):
    results, output, config, manifest = _setup(tmp_path)
    canonical = results / "current.txt"
    stale = results / "stale.txt"
    canonical.write_text(_log(("G x", "false"), ("G y", "true")), encoding="utf-8")
    stale.write_text(_log(("G x", "false"), ("G y", "false")), encoding="utf-8")
    summary = _run(results, output, config, manifest, [
        _entry("C", "M-1", "current.txt", expected_hash=sha256(canonical.read_bytes()).hexdigest()),
        _entry("C", "M-1", "stale.txt", canonical=False),
    ])
    index = json.loads((output / "canonical_index.json").read_text(encoding="utf-8"))
    assert summary["number_of_runs"] == 1
    assert summary["number_of_property_violations"] == 1
    assert len(index["verdicts"]) == 2
    assert all(row["source_output_path"] == "current.txt" for row in index["verdicts"])
    assert stale.exists()
    assert not (output / "runs" / "C" / "stale.json").exists()


def test_duplicate_log_path_is_rejected(tmp_path):
    results, output, config, manifest = _setup(tmp_path)
    (results / "one.txt").write_text(_log(("G x", "true"), ("G y", "true")), encoding="utf-8")
    with pytest.raises(ManifestError, match="duplicate log path"):
        _run(results, output, config, manifest, [
            _entry("C", "M-1", "one.txt"), _entry("C", "M-2", "one.txt")])
    assert not output.exists()


def test_duplicate_canonical_mutant_identity_is_rejected(tmp_path):
    results, output, config, manifest = _setup(tmp_path)
    for name in ("one.txt", "two.txt"):
        (results / name).write_text(_log(("G x", "true"), ("G y", "true")), encoding="utf-8")
    with pytest.raises(ManifestError, match="duplicate canonical identity"):
        _run(results, output, config, manifest, [
            _entry("C", "M-1", "one.txt"), _entry("C", "M-1", "two.txt")])


def test_missing_canonical_log_fails_without_substitution(tmp_path):
    results, output, config, manifest = _setup(tmp_path)
    (results / "other.txt").write_text(_log(("G x", "true"), ("G y", "true")), encoding="utf-8")
    with pytest.raises(ManifestError, match="missing canonical log"):
        _run(results, output, config, manifest, [_entry("C", "M-1", "missing.txt")])
    assert not output.exists()


def test_source_hash_mismatch_fails_before_writing(tmp_path):
    results, output, config, manifest = _setup(tmp_path)
    (results / "one.txt").write_text(_log(("G x", "true"), ("G y", "true")), encoding="utf-8")
    with pytest.raises(ManifestError, match="source hash mismatch"):
        _run(results, output, config, manifest, [
            _entry("C", "M-1", "one.txt", expected_hash="0" * 64)])
    assert not output.exists()


def test_two_violated_properties_are_one_mutant_with_violation(tmp_path):
    results, output, config, manifest = _setup(tmp_path)
    (results / "mutant.txt").write_text(_log(("G x", "false"), ("G y", "false")), encoding="utf-8")
    (results / "reference.txt").write_text(_log(("G x", "true"), ("G y", "true")), encoding="utf-8")
    summary = _run(results, output, config, manifest, [
        _entry("C", "M-1", "mutant.txt"), _entry("C", "reference", "reference.txt")])
    assert summary["number_of_runs"] == 2
    assert summary["number_of_properties_checked"] == 4
    assert summary["number_of_runs_with_violation"] == 1
    assert summary["number_of_property_violations"] == 2
    assert summary["number_of_unique_mutants_with_violation"] == 1
    assert summary["runs"][1]["number_of_property_violations"] == 0
    assert summary["runs"][1]["has_violation"] is False


def test_reference_run_alone_has_zero_violations(tmp_path):
    results, output, config, manifest = _setup(tmp_path)
    (results / "reference.txt").write_text(_log(("G x", "true"), ("G y", "true")), encoding="utf-8")
    summary = _run(results, output, config, manifest, [_entry("C", "reference", "reference.txt")])
    assert summary["number_of_runs"] == 1
    assert summary["number_of_properties_checked"] == 2
    assert summary["number_of_runs_with_violation"] == 0
    assert summary["number_of_property_violations"] == 0
    assert summary["number_of_unique_mutants_with_violation"] == 0


def test_pilot_manifest_selects_21_runs_from_23_preserved_logs(tmp_path):
    research = Path(__file__).resolve().parents[1]
    pilot = research / "elcon2027"
    result = extract_manifest(
        pilot / "witness_manifest.json",
        pilot / "results",
        tmp_path / "witnesses",
        pilot / "witness_config.json",
    )
    index = json.loads((tmp_path / "witnesses" / "canonical_index.json").read_text(encoding="utf-8"))
    assert result["number_of_runs"] == 21
    assert result["number_of_properties_checked"] == 98
    assert result["number_of_runs_with_violation"] == 18
    assert result["number_of_property_violations"] == 18
    assert result["number_of_unique_mutants_with_violation"] == 18
    assert result["number_of_noncanonical_manifest_entries"] == 2
    assert len(index["verdicts"]) == 98
    assert {row["source_output_path"] for row in index["verdicts"]}.isdisjoint({
        "E27-M01_G3_M-M1.txt", "E27-M01_G3_M-M3.txt"})

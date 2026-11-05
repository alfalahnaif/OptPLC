"""Extract only manifest-designated canonical nuXmv pilot runs."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any

from research.core.nuxmv_witness import Witness, parse_nuxmv_output, read_nuxmv_output, write_witnesses_json


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_HASH = re.compile(r"^[0-9a-fA-F]{64}$")


class ManifestError(ValueError):
    """The manifest cannot define an unambiguous canonical experiment."""


@dataclass(frozen=True)
class ManifestRun:
    case_id: str
    mutant_id: str
    log_path: str
    property_set: str
    canonical: bool
    expected_source_sha256: str | None


def _load_manifest(path: Path) -> tuple[list[ManifestRun], str]:
    raw = path.read_bytes()
    try:
        document = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"invalid manifest JSON: {path}") from exc
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise ManifestError("manifest schema_version must be 1")
    entries = document.get("runs")
    if not isinstance(entries, list) or not entries:
        raise ManifestError("manifest runs must be a nonempty list")

    runs: list[ManifestRun] = []
    seen_paths: set[str] = set()
    seen_canonical: set[tuple[str, str]] = set()
    for index, entry in enumerate(entries):
        required = {"case_id", "mutant_id", "log_path", "property_set", "canonical"}
        allowed = required | {"expected_source_sha256"}
        if not isinstance(entry, dict) or not required <= entry.keys() or entry.keys() - allowed:
            raise ManifestError(f"invalid manifest entry {index}: required fields or unknown fields")
        for field in ("case_id", "mutant_id", "property_set"):
            if not isinstance(entry[field], str) or not _IDENTIFIER.fullmatch(entry[field]):
                raise ManifestError(f"invalid {field} in manifest entry {index}")
        if type(entry["canonical"]) is not bool:
            raise ManifestError(f"canonical must be Boolean in manifest entry {index}")
        log_path = entry["log_path"]
        if not isinstance(log_path, str) or "\\" in log_path or not log_path:
            raise ManifestError(f"invalid log_path in manifest entry {index}")
        relative = PurePosixPath(log_path)
        if relative.is_absolute() or any(part in ("..", ".") for part in log_path.split("/")):
            raise ManifestError(f"log_path must stay inside results root: {log_path}")
        if relative.as_posix() != log_path:
            raise ManifestError(f"noncanonical log_path spelling: {log_path}")
        if log_path in seen_paths:
            raise ManifestError(f"duplicate log path: {log_path}")
        seen_paths.add(log_path)
        expected_hash = entry.get("expected_source_sha256")
        if expected_hash is not None and (not isinstance(expected_hash, str) or not _HASH.fullmatch(expected_hash)):
            raise ManifestError(f"invalid expected source hash for: {log_path}")
        identity = (entry["case_id"], entry["mutant_id"])
        if entry["canonical"] and identity in seen_canonical:
            raise ManifestError(f"duplicate canonical identity: {identity}")
        if entry["canonical"]:
            seen_canonical.add(identity)
        runs.append(ManifestRun(entry["case_id"], entry["mutant_id"], log_path,
                                entry["property_set"], entry["canonical"], expected_hash))
    if not seen_canonical:
        raise ManifestError("manifest has no canonical runs")
    return runs, sha256(raw).hexdigest()


def _resolve_canonical_log(results_root: Path, run: ManifestRun) -> Path:
    root = results_root.resolve()
    path = (root / run.log_path).resolve()
    if not path.is_relative_to(root):
        raise ManifestError(f"canonical log escapes results root: {run.log_path}")
    if not path.is_file():
        raise ManifestError(f"missing canonical log: {run.log_path}")
    return path


def _parse_run(run: ManifestRun, results_root: Path, config: dict[str, Any]) -> list[Witness]:
    if run.property_set not in config:
        raise ManifestError(f"unknown property_set: {run.property_set}")
    path = _resolve_canonical_log(results_root, run)
    raw = read_nuxmv_output(path)
    if run.expected_source_sha256 and raw.sha256.lower() != run.expected_source_sha256.lower():
        raise ManifestError(f"source hash mismatch: {run.log_path}")
    definition = config[run.property_set]
    witnesses = parse_nuxmv_output(
        raw.text,
        case_id=run.case_id,
        mutant_id=run.mutant_id,
        property_ids=definition["property_ids"],
        variable_roles=definition["variable_roles"],
        source_output_path=run.log_path,
        source_encoding=raw.encoding,
        source_sha256=raw.sha256,
    )
    expected_ids = set(definition["property_ids"].values())
    actual_ids = {witness.property_id for witness in witnesses}
    if actual_ids != expected_ids or len(witnesses) != len(expected_ids):
        raise ManifestError(f"incomplete property set for {run.case_id}/{run.mutant_id}: "
                            f"expected {sorted(expected_ids)}, got {sorted(actual_ids)}")
    return witnesses


def _run_row(run: ManifestRun, witnesses: list[Witness], witness_path: str) -> dict[str, Any]:
    violations = sum(w.verification_status == "VIOLATED" for w in witnesses)
    return {
        "case_id": run.case_id,
        "mutant_id": run.mutant_id,
        "log_path": run.log_path,
        "property_set": run.property_set,
        "witness_path": witness_path,
        "source_sha256": witnesses[0].source_sha256,
        "number_of_properties_checked": sum(w.verification_status in ("SATISFIED", "VIOLATED") for w in witnesses),
        "number_of_property_violations": violations,
        "has_violation": bool(violations),
    }


def _summary(rows: list[dict[str, Any]], manifest_hash: str, historical_count: int) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_sha256": manifest_hash,
        "number_of_runs": len(rows),
        "number_of_properties_checked": sum(row["number_of_properties_checked"] for row in rows),
        "number_of_runs_with_violation": sum(row["has_violation"] for row in rows),
        "number_of_property_violations": sum(row["number_of_property_violations"] for row in rows),
        "number_of_unique_mutants_with_violation": len({
            (row["case_id"], row["mutant_id"]) for row in rows
            if row["mutant_id"] != "reference" and row["has_violation"]
        }),
        "number_of_noncanonical_manifest_entries": historical_count,
        "runs": rows,
    }


def _write_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))


def extract_manifest(manifest_path: Path, results_root: Path, output_root: Path,
                     config_path: Path) -> dict[str, Any]:
    """Validate all canonical runs before writing witnesses, index, and summary."""
    runs, manifest_hash = _load_manifest(manifest_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    pending: list[tuple[Path, list[Witness]]] = []
    index_rows: list[dict[str, Any]] = []
    run_rows: list[dict[str, Any]] = []
    for run in runs:
        if not run.canonical:
            continue
        witnesses = _parse_run(run, results_root, config)
        relative_output = Path("runs") / run.case_id / f"{run.mutant_id}.json"
        pending.append((output_root / relative_output, witnesses))
        witness_path = relative_output.as_posix()
        run_rows.append(_run_row(run, witnesses, witness_path))
        index_rows.extend({
            "case_id": run.case_id,
            "mutant_id": run.mutant_id,
            "property_set": run.property_set,
            "property_id": witness.property_id,
            "verification_status": witness.verification_status,
            "source_output_path": run.log_path,
            "source_sha256": witness.source_sha256,
            "witness_path": witness_path,
        } for witness in witnesses)
    summary = _summary(run_rows, manifest_hash, len(runs) - len(run_rows))
    index = {"schema_version": 1, "manifest_sha256": manifest_hash, "verdicts": index_rows}
    for destination, witnesses in pending:
        write_witnesses_json(witnesses, destination)
    _write_json(output_root / "canonical_index.json", index)
    _write_json(output_root / "run_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract manifest-designated canonical G3 witnesses")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("research/elcon2027/witness_config.json"))
    args = parser.parse_args()
    summary = extract_manifest(args.manifest, args.results_root, args.output_root, args.config)
    print(f"Extracted {summary['number_of_runs']} canonical runs, "
          f"{summary['number_of_properties_checked']} checked properties, "
          f"{summary['number_of_property_violations']} property violations")


if __name__ == "__main__":
    main()

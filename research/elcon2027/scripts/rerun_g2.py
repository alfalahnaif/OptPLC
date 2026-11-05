"""Re-run verification gate G2 over every ElCon-EE 2027 pilot case.

Read-only with respect to the pilot: it reads `cases/` and refuses to write
anywhere inside `research/elcon2027/results/`. Added in backlog item R1-A to
replace the original per-case scripts, which read from hard-coded /tmp paths
and so could not be reproduced on a clean machine.

Usage (from the repository root):

    backend/.venv/Scripts/python.exe research/elcon2027/scripts/rerun_g2.py \
        --out /path/outside/results/g2_rerun.json

`app.config` validates settings at import time, so a provider key must be set
even though no LLM is contacted: OPENAI_API_KEY=dummy-not-used is enough.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = (REPO_ROOT / "research" / "elcon2027" / "results").resolve()
CASES_DIR = REPO_ROOT / "research" / "elcon2027" / "cases"

sys.path.insert(0, str(REPO_ROOT / "backend"))

import yaml  # noqa: E402

# Case -> (folder, dotted validator class name, domain label). The validators are
# imported lazily in main(), after the output-path guard, so that a bad --out is
# reported even when the backend settings cannot be loaded.
CASES = {
    "E27-M01": ("E27-M01-motor", "MotorControlValidator", "Motor Control"),
    "E27-I01": ("E27-I01-interlock", "SafetyInterlockValidator", "Safety Interlock"),
    "E27-B01": ("E27-B01-batch", "SequentialBatchValidator", "Sequential Batch"),
}


def signal_names(signals_yaml: Path) -> set[str]:
    """Collect every signal name from a case's signals.yaml, whatever its shape."""
    names: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ("name", "signal") and isinstance(value, (str, int)):
                    names.add(str(value))
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, str):
            names.add(node)

    walk(yaml.safe_load(signals_yaml.read_text(encoding="utf-8")))
    return names


def run_case(case_dir: Path, validator_cls: type, domain: str) -> dict:
    names = signal_names(case_dir / "signals.yaml")
    validator = validator_cls()
    sources = [("reference", case_dir / "reference.st")] + [
        (path.stem.split("_", 1)[0], path)
        for path in sorted((case_dir / "mutants").glob("*.st"))
    ]
    per_file = {}
    for label, path in sources:
        checks = validator.validate(
            source=path.read_text(encoding="utf-8"), signal_names=names
        )
        failed = [check.id for check in checks if check.status != "passed"]
        per_file[label] = {
            "overall": "FAIL" if failed else "PASS",
            "failed_rules": failed,
            "rules_evaluated": len(checks),
        }
    mutants = len(sources) - 1
    detected = sum(
        1 for label, r in per_file.items() if label != "reference" and r["overall"] == "FAIL"
    )
    return {
        "domain": domain,
        "mutants": mutants,
        "g2_detected": detected,
        "g2_mdr_percent": round(100 * detected / mutants, 2),
        "reference_overall": per_file["reference"]["overall"],
        "signals": sorted(names),
        "per_file": per_file,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="where to write the JSON report; must be outside research/elcon2027/results/",
    )
    args = parser.parse_args()

    out = args.out.resolve()
    if RESULTS_DIR == out.parent or RESULTS_DIR in out.parents:
        parser.error(
            f"refusing to write inside the stored pilot results ({RESULTS_DIR}); "
            "pick a path outside it"
        )

    import app.agents.validation_agent as va

    report = {
        case: run_case(CASES_DIR / folder, getattr(va, cls_name), domain)
        for case, (folder, cls_name, domain) in CASES.items()
    }

    for case, result in report.items():
        print(
            f"{case} ({result['domain']}): G2 detected "
            f"{result['g2_detected']}/{result['mutants']} = {result['g2_mdr_percent']}%  "
            f"reference={result['reference_overall']}"
        )
        for label, entry in result["per_file"].items():
            print(f"    {label:10s} {entry['overall']:4s} failed={entry['failed_rules']}")

    detected = sum(r["g2_detected"] for r in report.values())
    mutants = sum(r["mutants"] for r in report.values())
    total_mdr = round(100 * detected / mutants, 2)
    print(f"\nTOTAL G2: {detected}/{mutants} = {total_mdr}%")
    print("Expected from the October 2026 run: 4/18 = 22.22%")

    report["_total"] = {
        "mutants": mutants,
        "g2_detected": detected,
        "g2_mdr_percent": total_mdr,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"report written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

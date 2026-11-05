"""Command-line adapter for research-local nuXmv witness extraction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.core.nuxmv_witness import parse_nuxmv_output, read_nuxmv_output, write_witnesses_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract structured nuXmv verdicts and counterexamples")
    parser.add_argument("input", type=Path, help="raw nuXmv output text")
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--mutant-id", required=True)
    parser.add_argument("--property-map", type=Path, required=True, help="JSON: specification text to property ID")
    parser.add_argument("--roles", type=Path, required=True, help="JSON: variable name to input/output/state")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    raw = read_nuxmv_output(args.input)
    property_ids = json.loads(args.property_map.read_text(encoding="utf-8"))
    variable_roles = json.loads(args.roles.read_text(encoding="utf-8"))
    if not isinstance(property_ids, dict) or not isinstance(variable_roles, dict):
        parser.error("property map and roles must each be a JSON object")
    witnesses = parse_nuxmv_output(
        raw.text,
        case_id=args.case_id,
        mutant_id=args.mutant_id,
        property_ids=property_ids,
        variable_roles=variable_roles,
        source_output_path=str(args.input),
        source_encoding=raw.encoding,
        source_sha256=raw.sha256,
    )
    write_witnesses_json(witnesses, args.output)


if __name__ == "__main__":
    main()

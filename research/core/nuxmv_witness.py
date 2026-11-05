"""Deterministic parser for nuXmv's textual LTL counterexample output."""

from __future__ import annotations

import json
import re
from hashlib import sha256
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, Mapping


Status = Literal["SATISFIED", "VIOLATED", "ERROR", "UNKNOWN"]
Role = Literal["input", "output", "state"]
Value = bool | str

_SPEC = re.compile(r"^\s*-- specification\s+(.+?)\s+is\s+(true|false|unknown|error)\s*$", re.I)
_VERSION = re.compile(r"^\*\*\* This is nuXmv\s+(\S+)", re.M)
_STATE = re.compile(r"^\s*-> State:\s+(\d+)\.(\d+)\s+<-\s*$")
_ASSIGNMENT = re.compile(r"^\s+(.+?)\s+=\s+(.+?)\s*$")
_LOOP = re.compile(r"^\s*-- Loop starts here\s*$")
_ERROR = re.compile(r"\b(?:error|fatal error)\s*:", re.I)


class WitnessParseError(ValueError):
    """The nuXmv output cannot be represented without guessing."""


@dataclass(frozen=True)
class WitnessStep:
    index: int
    nuxmv_state: str
    inputs: dict[str, Value]
    outputs: dict[str, Value]
    state: dict[str, Value]
    changed_variables: list[str]
    observed_variables: list[str]
    carried_variables: list[str]
    loop_start: bool


@dataclass(frozen=True)
class WitnessTransition:
    from_index: int
    to_index: int
    changed_variables: list[str]
    loop_back: bool


@dataclass(frozen=True)
class Witness:
    case_id: str
    mutant_id: str
    property_id: str
    specification: str
    verification_status: Status
    steps: list[WitnessStep]
    transitions: list[WitnessTransition]
    tool: str
    tool_version: str | None
    source_output_path: str
    source_encoding: str | None
    source_sha256: str | None
    raw_source: str


@dataclass(frozen=True)
class RawOutput:
    text: str
    encoding: str
    sha256: str


def read_nuxmv_output(path: Path) -> RawOutput:
    """Decode UTF-8 or BOM-marked UTF-16 without changing line endings."""
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        encoding = "utf-16"
    elif raw.startswith(b"\xef\xbb\xbf"):
        encoding = "utf-8-sig"
    else:
        encoding = "utf-8"
    try:
        decoded = raw.decode(encoding)
    except UnicodeError as exc:
        raise WitnessParseError(f"cannot decode nuXmv output as {encoding}: {path}") from exc
    return RawOutput(decoded, encoding, sha256(raw).hexdigest())


def _value(text: str) -> Value:
    if text.upper() == "TRUE":
        return True
    if text.upper() == "FALSE":
        return False
    return text


def _key(specification: str) -> str:
    return " ".join(specification.split())


def _steps(lines: list[str], roles: Mapping[str, Role]) -> tuple[list[WitnessStep], list[WitnessTransition]]:
    states: list[tuple[str, dict[str, Value], bool]] = []
    trace_type = False
    loop_next = False
    for line in lines:
        if not line.strip() or line.strip() == "-- as demonstrated by the following execution sequence":
            continue
        if line.startswith("Trace Description:"):
            continue
        if line.startswith("Trace Type:"):
            if line.split(":", 1)[1].strip() != "Counterexample":
                raise WitnessParseError(f"unsupported trace type: {line}")
            trace_type = True
            continue
        if _LOOP.fullmatch(line):
            if loop_next or any(state[2] for state in states):
                raise WitnessParseError("multiple loop markers")
            loop_next = True
            continue
        header = _STATE.fullmatch(line)
        if header:
            number = f"{header[1]}.{header[2]}"
            if states and int(header[2]) != len(states) + 1:
                raise WitnessParseError(f"nonsequential state: {number}")
            states.append((number, {}, loop_next))
            loop_next = False
            continue
        if line.lstrip().startswith("--"):
            raise WitnessParseError(f"unsupported trace marker: {line}")
        assignment = _ASSIGNMENT.fullmatch(line)
        if assignment and states:
            name, raw_value = assignment.groups()
            if name in states[-1][1]:
                raise WitnessParseError(f"duplicate assignment for {name}")
            states[-1][1][name] = _value(raw_value)
            continue
        raise WitnessParseError(f"unrecognized trace line or assignment: {line}")

    if not trace_type or not states or not states[0][1] or loop_next:
        raise WitnessParseError("violated property lacks a complete counterexample trace")
    roster = list(states[0][1])
    for _, assignments, _ in states[1:]:
        new_names = assignments.keys() - states[0][1].keys()
        if new_names:
            raise WitnessParseError(f"variable missing from initial state: {sorted(new_names)}")
    missing_roles = set(roster) - roles.keys()
    if missing_roles:
        raise WitnessParseError(f"variable roles missing: {sorted(missing_roles)}")
    if any(roles[name] not in ("input", "output", "state") for name in roster):
        raise WitnessParseError("variable role must be input, output, or state")

    steps: list[WitnessStep] = []
    transitions: list[WitnessTransition] = []
    current: dict[str, Value] = {}
    for index, (number, assignments, loop_start) in enumerate(states):
        previous = current.copy()
        current.update(assignments)
        changed = [name for name in roster if index and previous[name] != current[name]]
        step = WitnessStep(
            index=index,
            nuxmv_state=number,
            inputs={name: current[name] for name in roster if roles[name] == "input"},
            outputs={name: current[name] for name in roster if roles[name] == "output"},
            state={name: current[name] for name in roster if roles[name] == "state"},
            changed_variables=changed,
            observed_variables=[name for name in roster if name in assignments],
            carried_variables=[name for name in roster if name not in assignments],
            loop_start=loop_start,
        )
        steps.append(step)
        if index:
            transitions.append(WitnessTransition(index - 1, index, changed, False))
    loop_indexes = [step.index for step in steps if step.loop_start]
    if loop_indexes:
        target = loop_indexes[0]
        last = {**steps[-1].inputs, **steps[-1].outputs, **steps[-1].state}
        first = {**steps[target].inputs, **steps[target].outputs, **steps[target].state}
        changed = [name for name in roster if last[name] != first[name]]
        transitions.append(WitnessTransition(len(steps) - 1, target, changed, True))
    return steps, transitions


def parse_nuxmv_output(
    raw_source: str,
    *,
    case_id: str,
    mutant_id: str,
    property_ids: Mapping[str, str],
    variable_roles: Mapping[str, Role],
    source_output_path: str,
    source_encoding: str | None = None,
    source_sha256: str | None = None,
) -> list[Witness]:
    """Parse all verdicts; property_ids keys are nuXmv specification texts.

    Whitespace in a specification key is collapsed. The caller must explicitly
    identify each property and each variable role; no IDs or values are guessed.
    """
    if not all((raw_source, case_id, mutant_id, source_output_path)):
        raise WitnessParseError("raw output and metadata must be nonempty")
    lines = raw_source.splitlines()
    matches = [(i, match) for i, line in enumerate(lines) if (match := _SPEC.fullmatch(line))]
    version = _VERSION.search(raw_source)
    if not matches:
        if _ERROR.search(raw_source):
            run_id = property_ids.get("__run__")
            if not run_id:
                raise WitnessParseError("nuXmv run error needs an explicit __run__ property ID")
            return [Witness(case_id, mutant_id, run_id, "<run>", "ERROR", [], [],
                            "nuXmv", version[1] if version else None,
                            source_output_path, source_encoding, source_sha256, raw_source)]
        raise WitnessParseError("no recognized nuXmv specification verdict")
    if any(_ERROR.search(line) for line in lines if not line.startswith("***")):
        raise WitnessParseError("nuXmv error mixed with property verdicts")
    for line in lines:
        if re.match(r"^\s*-- specification\b", line) and not _SPEC.fullmatch(line):
            raise WitnessParseError(f"malformed specification verdict: {line}")
    ids: dict[str, str] = {}
    for specification, identity in property_ids.items():
        key = _key(specification)
        if key in ids and ids[key] != identity:
            raise WitnessParseError(f"conflicting property IDs for: {specification}")
        ids[key] = identity
    results: list[Witness] = []
    seen: set[str] = set()
    for position, (start, match) in enumerate(matches):
        specification = match[1].strip()
        key = _key(specification)
        if key in seen:
            raise WitnessParseError(f"duplicate specification: {specification}")
        seen.add(key)
        if key not in ids or not ids[key]:
            raise WitnessParseError(f"missing property ID for: {specification}")
        end = matches[position + 1][0] if position + 1 < len(matches) else len(lines)
        status: Status = {"true": "SATISFIED", "false": "VIOLATED", "error": "ERROR", "unknown": "UNKNOWN"}[match[2].lower()]
        block = lines[start + 1:end]
        if status == "VIOLATED":
            steps, transitions = _steps(block, variable_roles)
        else:
            if any(line.strip() for line in block):
                raise WitnessParseError(f"unexpected content for {status} property: {specification}")
            steps, transitions = [], []
        results.append(Witness(case_id, mutant_id, ids[key], specification, status,
                               steps, transitions, "nuXmv", version[1] if version else None,
                               source_output_path, source_encoding, source_sha256, raw_source))
    return results


def write_witnesses_json(witnesses: list[Witness], destination: Path) -> None:
    """Store parsed verdicts and exact raw output text as UTF-8 JSON."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(
        (json.dumps([asdict(witness) for witness in witnesses], indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    )

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal

from app.schemas.contracts import (
    CodeArtifact,
    PlanObject,
    ValidationProperty,
    ValidationReport,
    ValidationSafetyResult,
)

ValidationMode = Literal["static", "formal"]


class ValidationAgent:
    def __init__(self, mode: ValidationMode = "static") -> None:
        self.mode = mode

    def validate(
        self,
        *,
        project_id: str,
        artifact: CodeArtifact,
        plan: PlanObject,
    ) -> ValidationReport:
        if self.mode == "formal":
            raise NotImplementedError("ValidationAgent formal mode is reserved for future MATIEC/nuXmv/PLCverif integration.")
        if self.mode != "static":
            raise ValueError(f"Unsupported ValidationAgent mode: {self.mode}")

        syntax_errors = self._syntax_errors(artifact.source)
        safety_results = [] if syntax_errors else self._safety_results(artifact.source, plan)
        failed_safety = [result for result in safety_results if result.status == "failed"]
        formal_errors = [result.details or result.description for result in failed_safety]

        if syntax_errors:
            status = "SYNTAX_ERROR"
            summary = "Structured Text syntax/static checks failed."
        elif formal_errors:
            status = "FORMAL_VIOLATION"
            summary = "Static safety checks found domain-specific violations."
        else:
            status = "VERIFIED"
            summary = "Structured Text syntax and static safety checks passed."

        counterexamples = self._counterexamples(failed_safety)
        properties = [
            ValidationProperty(
                id=result.id,
                description=result.description,
                status=result.status,
            )
            for result in safety_results
        ]

        return ValidationReport(
            projectId=project_id,
            artifactId=artifact.artifactId,
            iteration=artifact.iteration,
            status=status,
            syntaxPassed=not syntax_errors,
            formalPassed=not syntax_errors and not formal_errors,
            solver="static.v1",
            validator="static.v1",
            checkedAt=self._utc_now(),
            summary=summary,
            syntaxErrors=syntax_errors,
            formalErrors=formal_errors,
            safetyResults=safety_results,
            properties=properties,
            errors=[*syntax_errors, *formal_errors],
            counterexample=counterexamples or None,
            counterexamples=counterexamples,
        )

    def _syntax_errors(self, source: str) -> list[str]:
        errors: list[str] = []
        if not source.strip():
            return ["CodeArtifact source is empty."]

        uncommented = self._strip_comments(source)
        upper = uncommented.upper()

        has_program = bool(re.search(r"\bPROGRAM\s+[A-Z_][A-Z0-9_]*", upper))
        has_function_block = bool(re.search(r"\bFUNCTION_BLOCK\s+[A-Z_][A-Z0-9_]*", upper))
        if not (has_program or has_function_block):
            errors.append("PROGRAM or FUNCTION_BLOCK declaration is required.")
        if has_program and not re.search(r"\bEND_PROGRAM\b", upper):
            errors.append("END_PROGRAM is required for PROGRAM blocks.")
        if has_function_block and not re.search(r"\bEND_FUNCTION_BLOCK\b", upper):
            errors.append("END_FUNCTION_BLOCK is required for FUNCTION_BLOCK blocks.")

        if not re.search(r"\bVAR_INPUT\b", upper):
            errors.append("VAR_INPUT block is required.")
        if not re.search(r"\bVAR_OUTPUT\b", upper):
            errors.append("VAR_OUTPUT block is required.")

        var_blocks = re.findall(r"^\s*VAR(?:_INPUT|_OUTPUT)?\b", upper, flags=re.MULTILINE)
        end_vars = re.findall(r"^\s*END_VAR\b", upper, flags=re.MULTILINE)
        if len(end_vars) < len(var_blocks):
            errors.append("Each VAR block must be closed with END_VAR.")

        for start, end, name in [
            ("IF", "END_IF", "IF"),
            ("CASE", "END_CASE", "CASE"),
            ("FOR", "END_FOR", "FOR"),
            ("WHILE", "END_WHILE", "WHILE"),
        ]:
            start_count = len(re.findall(rf"\b{start}\b", upper))
            end_count = len(re.findall(rf"\b{end}\b", upper))
            if end_count < start_count:
                errors.append(f"{name} statements must be closed with {end}.")

        declared = self._declared_variables(source)
        for assigned in self._assigned_variables(source):
            if assigned not in declared:
                errors.append(f"Assigned variable '{assigned}' is not declared.")

        for line_number, line in enumerate(uncommented.splitlines(), start=1):
            stripped = line.strip()
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s*=(?!=)", stripped):
                errors.append(f"Line {line_number}: assignments must use ':='.")
            if re.search(r"\b(?:true|false)\b", stripped):
                errors.append(f"Line {line_number}: boolean constants must be TRUE or FALSE.")

        unsupported_patterns = {
            r"\bdef\s+[A-Za-z_]": "Python function syntax is not supported.",
            r"\bimport\s+[A-Za-z_]": "Python/JavaScript import syntax is not supported.",
            r"\bconsole\.log\b": "JavaScript syntax is not supported.",
            r"\bfunction\s+[A-Za-z_]": "JavaScript function syntax is not supported.",
            r"#include\s*<": "C/C++ include syntax is not supported.",
            r"\bstd::": "C++ namespace syntax is not supported.",
            r"=>": "Arrow-function pseudocode is not supported.",
        }
        for pattern, message in unsupported_patterns.items():
            if re.search(pattern, uncommented):
                errors.append(message)

        return list(dict.fromkeys(errors))

    def _safety_results(self, source: str, plan: PlanObject) -> list[ValidationSafetyResult]:
        names = {signal.name for signal in [*plan.inputs, *plan.outputs]}

        if {"Start_PB", "Stop_PB", "E_Stop", "Overload", "Motor_Run"}.issubset(names):
            return self._motor_safety(source)
        if {"Vehicle_Detect", "Ped_Request", "Red_Light", "Green_Light", "Ped_Walk"}.issubset(names):
            return self._traffic_safety(source)
        if {"Level_PV", "Low_SP", "High_SP", "Inlet_Valve"}.issubset(names):
            return self._tank_safety(source, plan)
        if {"Guard_Closed", "Machine_Enable", "Trip_Lamp"}.issubset(names):
            return self._safety_interlock_safety(source)
        if {"Start_Batch", "Fill_Valve", "Heater", "Drain_Valve"}.issubset(names):
            return self._batch_safety(source)

        return [
            self._result(
                "GEN-1",
                "Generic fallback must gate process enable with a safe run/fault state",
                "PROCESS_ENABLE" in source.upper() and "FAULT_STATE" in source.upper(),
            )
        ]

    def _motor_safety(self, source: str) -> list[ValidationSafetyResult]:
        upper = source.upper()
        motor_lines = [line.upper().strip() for line in source.splitlines() if re.match(r"\s*Motor_Run\s*:=", line)]
        motor_expr = " ".join(motor_lines)
        return [
            self._result(
                "MC-1",
                "Motor output must be forced FALSE when emergency stop is active",
                "E_STOP" in upper and ("SAFETY_OK" in motor_expr or "NOT E_STOP" in motor_expr or "FAULT_STATE" in motor_expr),
                "Motor_Run is not visibly gated by E_Stop or the safety/fault state.",
            ),
            self._result(
                "MC-2",
                "Motor output must be forced FALSE when overload is active",
                "OVERLOAD" in upper and ("SAFETY_OK" in motor_expr or "FAULT_STATE" in motor_expr),
                "Motor_Run is not visibly gated by overload or the safety/fault state.",
            ),
            self._result(
                "MC-3",
                "Auto-restart must require explicit operator reset after a safety trip",
                "RESET_PB" in upper and "FAULT_STATE" in upper,
                "Fault latching and Reset_PB handling are required to prevent auto-restart.",
            ),
        ]

    def _traffic_safety(self, source: str) -> list[ValidationSafetyResult]:
        upper = source.upper()
        conflicting_direct = "GREEN_LIGHT := TRUE" in upper and "PED_WALK := TRUE" in upper
        protected_pedestrian = "PED_WALK := RED_LIGHT AND PED_REQUEST" in upper or "PED_WALK := PHASE_RED" in upper
        non_conflicting_green = "GREEN_LIGHT := NOT RED_LIGHT AND NOT AMBER_LIGHT" in upper
        return [
            self._result(
                "TL-1",
                "Vehicle green and pedestrian walk must not be TRUE at the same time",
                not conflicting_direct and protected_pedestrian and non_conflicting_green,
                "Traffic logic can permit conflicting green/walk outputs.",
            ),
            self._result(
                "TL-2",
                "Traffic phases should define a safe transition condition",
                "EMERGENCY_FLASH" in upper or "PHASE_RED" in upper or "PHASE_AMBER" in upper,
                "No explicit safe phase/transition guard was found.",
            ),
        ]

    def _tank_safety(self, source: str, plan: PlanObject) -> list[ValidationSafetyResult]:
        upper = source.upper()
        real_names = {signal.name for signal in plan.inputs if signal.type == "REAL"}
        return [
            self._result(
                "TK-1",
                "Level and setpoint variables should be REAL typed",
                {"Level_PV", "Low_SP", "High_SP"}.issubset(real_names),
                "Tank level/setpoint inputs must use REAL signal types.",
            ),
            self._result(
                "TK-2",
                "Inlet valve must close or change state at high-level condition",
                "INLET_VALVE := FALSE" in upper and ("HIGH_SP" in upper or "HIGHHIGH_SP" in upper),
                "High-level handling does not visibly close Inlet_Valve.",
            ),
            self._result(
                "TK-3",
                "Low-level condition should be handled before filling",
                "LOW_SP" in upper and ("FILL_REQUEST" in upper or "LEVEL_PV <=" in upper),
                "Low-level filling condition was not found.",
            ),
        ]

    def _safety_interlock_safety(self, source: str) -> list[ValidationSafetyResult]:
        upper = source.upper()
        return [
            self._result(
                "SI-1",
                "Safety interlock must fail safe on unsafe permissive conditions",
                "PERMISSIVE_OK" in upper and "TRIP_STATE" in upper,
                "No fail-safe permissive/trip state was found.",
            ),
            self._result(
                "SI-2",
                "Unsafe condition should force actuator output FALSE",
                "MACHINE_ENABLE := PERMISSIVE_OK AND NOT TRIP_STATE" in upper,
                "Machine_Enable is not gated by permissive and trip state.",
            ),
        ]

    def _batch_safety(self, source: str) -> list[ValidationSafetyResult]:
        upper = source.upper()
        return [
            self._result(
                "BT-1",
                "Sequential batch must use a state/step variable",
                re.search(r"\bSTEP\s*:\s*INT\b", upper) is not None and "CASE STEP OF" in upper,
                "No INT Step state machine was found.",
            ),
            self._result(
                "BT-2",
                "Emergency stop or abort condition should reset the batch safely",
                "STOP_BATCH" in upper or "ABORT" in upper or "E_STOP" in upper,
                "No stop/abort condition was found.",
            ),
            self._result(
                "BT-3",
                "Invalid step fallback should return to a safe idle state",
                "ELSE" in upper and "STEP := 0" in upper,
                "No invalid-step fallback to idle was found.",
            ),
        ]

    @staticmethod
    def _result(
        result_id: str,
        description: str,
        passed: bool,
        details: str | None = None,
    ) -> ValidationSafetyResult:
        return ValidationSafetyResult(
            id=result_id,
            description=description,
            status="passed" if passed else "failed",
            details=None if passed else details,
        )

    @staticmethod
    def _counterexamples(failed_safety: list[ValidationSafetyResult]) -> list[dict[str, bool | int | float | str]]:
        return [
            {
                "step": index,
                "property": result.id,
                "violation": result.details or result.description,
            }
            for index, result in enumerate(failed_safety, start=1)
        ]

    @staticmethod
    def _strip_comments(source: str) -> str:
        without_block = re.sub(r"\(\*.*?\*\)", "", source, flags=re.DOTALL)
        return re.sub(r"//.*", "", without_block)

    @classmethod
    def _declared_variables(cls, source: str) -> set[str]:
        declared: set[str] = set()
        inside_var = False
        for raw_line in source.splitlines():
            line = cls._strip_comments(raw_line).strip()
            upper = line.upper()
            if re.match(r"^VAR(?:_INPUT|_OUTPUT)?\b", upper):
                inside_var = True
                continue
            if upper.startswith("END_VAR"):
                inside_var = False
                continue
            if inside_var:
                match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(BOOL|INT|REAL|TIME|STRING)\s*;", line, flags=re.IGNORECASE)
                if match:
                    declared.add(match.group(1))
        return declared

    @classmethod
    def _assigned_variables(cls, source: str) -> set[str]:
        assigned: set[str] = set()
        uncommented = cls._strip_comments(source)
        for line in uncommented.splitlines():
            match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:=", line)
            if match:
                assigned.add(match.group(1))
        return assigned

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

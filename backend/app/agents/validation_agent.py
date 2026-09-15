from __future__ import annotations

import asyncio
import logging
import re
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Literal

from app.schemas.contracts import (
    CodeArtifact,
    PlanObject,
    ValidationProperty,
    ValidationReport,
    ValidationSafetyResult,
)
from app.services.st_syntax_check import PARSER_CHECK_LABEL, ParserCheck, strip_comments_and_strings
from app.services.transpiler_service import StToSmvTranspiler
from app.services.validation_service import MatiecValidator, PLCVerifValidator

ValidationMode = Literal["static", "formal"]
logger = logging.getLogger(__name__)


class DomainValidator(ABC):
    """Base class for all domain-specific validators."""

    domain_id: str = ""
    domain_name: str = ""
    rule_prefix: str = ""

    @abstractmethod
    def detect(
        self,
        signal_names: set[str],
        source: str,
        plan_domain: str,
    ) -> bool:
        """Return True if this validator applies to the given code."""

    @abstractmethod
    def validate(
        self,
        source: str,
        signal_names: set[str],
    ) -> list[ValidationSafetyResult]:
        """Run domain safety rules. Return list of results."""

    @staticmethod
    def _rule(
        rule_id: str,
        description: str,
        passed: bool,
        details: str | None = None,
    ) -> ValidationSafetyResult:
        return ValidationSafetyResult(
            id=rule_id,
            description=description,
            status="passed" if passed else "failed",
            details=details if not passed else None,
        )


class SequentialBatchValidator(DomainValidator):
    domain_id = "sequential_batch"
    domain_name = "Sequential Batch"
    rule_prefix = "BT"

    def detect(self, signal_names: set[str], source: str, plan_domain: str) -> bool:
        upper = source.upper()
        name_set = {n.upper() for n in signal_names}
        if {"START_BATCH", "FILL_VALVE", "HEATER", "DRAIN_VALVE"}.issubset(name_set):
            return True
        has_fill = any("FILL" in n for n in name_set)
        has_drain = any("DRAIN" in n for n in name_set)
        has_step = (
            re.search(r"\bCASE\b", upper) is not None
            or re.search(r"\b\w*STEP\w*\s*:\s*INT\b", upper) is not None
        )
        plan_domain_lower = plan_domain.lower()
        domain_match = "batch" in plan_domain_lower or "sequence" in plan_domain_lower
        return (has_fill and has_drain) or (domain_match and has_step)

    def validate(self, source: str, signal_names: set[str]) -> list[ValidationSafetyResult]:
        upper = source.upper()
        lines = source.splitlines()
        has_fill_signal = any("FILL" in n.upper() for n in signal_names)
        has_drain_signal = any("DRAIN" in n.upper() for n in signal_names)
        has_abort_signal = any("ABORT" in n.upper() for n in signal_names)
        has_reset_signal = any("RESET" in n.upper() for n in signal_names)
        has_estop_signal = any("E_STOP" in n.upper() or "EMERGENCY" in n.upper() for n in signal_names)
        R = self._rule
        results: list[ValidationSafetyResult] = []

        has_case = re.search(r"\bCASE\s+\w+\s+OF\b", upper) is not None
        has_step_int = re.search(r"\b\w*(?:STEP|STATE)\w*\s*:\s*INT\b", upper) is not None
        results.append(
            R(
                "BT-1",
                "Sequential batch must use CASE state machine with INT step variable",
                has_case or has_step_int,
                "No CASE state machine or INT step variable found",
            )
        )

        case_blocks = re.findall(r"CASE\s+\w+\s+OF(.*?)END_CASE", source, re.DOTALL | re.IGNORECASE)
        has_else = any("ELSE" in block.upper() for block in case_blocks)
        results.append(
            R(
                "BT-2",
                "CASE statement should have ELSE branch setting outputs to FALSE",
                has_else or not case_blocks,
                "CASE missing ELSE branch; undefined state may keep outputs energized",
            )
        )

        has_estop = re.search(r"\bEMERGENCY_STOP\b|\bE_STOP\b", upper) is not None
        has_abort = re.search(r"\bABORT\b", upper) is not None
        estop_abort_ok = (
            (not has_estop_signal and not has_abort_signal)
            or ((not has_estop_signal or has_estop) and (not has_abort_signal or has_abort))
        )
        missing_parts = []
        if has_estop_signal and not has_estop:
            missing_parts.append("Emergency_Stop")
        if has_abort_signal and not has_abort:
            missing_parts.append("Abort")
        results.append(
            R(
                "BT-3",
                "Emergency stop and abort should be handled when defined by the scenario",
                estop_abort_ok,
                f"Missing handling for: {', '.join(missing_parts)}" if missing_parts else None,
            )
        )

        has_fault = re.search(r"\bFAULT\w*\b", upper) is not None
        fault_ok = has_fault or not (has_estop_signal or has_abort_signal)
        results.append(
            R(
                "BT-4",
                "Fault state should be latched to prevent automatic restart after a trip",
                fault_ok,
                "No fault latch variable (e.g. Fault_State/Fault_Latched) found",
            )
        )

        fill_true_lines = [
            idx
            for idx, line in enumerate(lines)
            if "FILL_VALVE" in line.upper() and ":= TRUE" in line.upper()
        ]
        drain_true_lines = [
            idx
            for idx, line in enumerate(lines)
            if "DRAIN_VALVE" in line.upper() and ":= TRUE" in line.upper()
        ]
        conflict = any(abs(fill_idx - drain_idx) < 4 for fill_idx in fill_true_lines for drain_idx in drain_true_lines)
        conflict_check_applicable = has_fill_signal and has_drain_signal
        results.append(
            R(
                "BT-5",
                "Fill_Valve and Drain_Valve must never be TRUE simultaneously",
                (not conflict) if conflict_check_applicable else True,
                "Fill_Valve and Drain_Valve are both set TRUE in the same code context",
            )
        )

        last_case = max((m.start() for m in re.finditer(r"\bCASE\b", upper)), default=-1)
        last_estop = max((m.start() for m in re.finditer(r"\bEMERGENCY_STOP\b|\bE_STOP\b", upper)), default=-1)
        scan_ok = (last_case == -1 or last_estop == -1 or last_estop > last_case)
        results.append(
            R(
                "BT-6",
                "Safety force-off should execute after output assignments in scan order",
                scan_ok,
                "Emergency stop check appears before CASE block and may be overridden",
            )
        )

        has_reset = re.search(r"\bRESET_PB\b", upper) is not None
        reset_guarded = re.search(
            r"RESET_PB\s+AND\s+.{0,100}(?:NOT\s+EMERGENCY_STOP|NOT\s+E_STOP|NOT\s+ABORT|SAFETY_OK)",
            upper,
            re.DOTALL,
        ) is not None
        reset_ok = (not has_reset_signal) or (not has_reset) or reset_guarded
        results.append(
            R(
                "BT-7",
                "Reset_PB should only clear faults when safety conditions are healthy",
                reset_ok,
                "Reset_PB appears to clear faults without explicit safety health checks",
            )
        )

        return results


class MotorControlValidator(DomainValidator):
    domain_id = "motor_control"
    domain_name = "Motor Control"
    rule_prefix = "MC"

    def detect(self, signal_names: set[str], source: str, plan_domain: str) -> bool:
        name_set = {n.upper() for n in signal_names}
        has_motor = any("MOTOR" in n or "MOTOR_RUN" in n or "RUN" in n for n in name_set)
        has_stop = any("STOP" in n for n in name_set)
        has_start = any("START" in n for n in name_set)
        domain_hint = plan_domain.lower()
        domain_match = "motor" in domain_hint or "conveyor" in domain_hint
        return (has_motor and has_stop and has_start) or domain_match

    def validate(self, source: str, signal_names: set[str]) -> list[ValidationSafetyResult]:
        upper = source.upper()
        name_set = {n.upper() for n in signal_names}
        has_motor_signal = any("MOTOR" in n or "RUN" in n for n in name_set)
        has_start_signal = any("START" in n for n in name_set)
        has_stop_signal = any("STOP" in n or "E_STOP" in n or "EMERGENCY" in n for n in name_set)
        has_overload_signal = any("OVERLOAD" in n or "OVER_LOAD" in n for n in name_set)
        R = self._rule

        has_estop_off = re.search(
            r"(?:E_STOP|EMERGENCY_STOP|STOP_PB|OVERLOAD).{0,120}:=\s*FALSE",
            upper,
            re.DOTALL,
        ) is not None
        mc1_passed = (not has_motor_signal) or (not has_stop_signal and not has_overload_signal) or has_estop_off

        has_start_interlock = (
            re.search(r"START_PB\s+AND\s+NOT\s+(?:STOP|FAULT|E_STOP|OVERLOAD)", upper) is not None
            or re.search(r"NOT\s+(?:STOP|E_STOP).{0,80}START_PB", upper, re.DOTALL) is not None
        )
        mc2_passed = (not has_start_signal) or has_start_interlock

        has_fault = re.search(r"\bFAULT\w*\b", upper) is not None
        mc3_passed = has_fault or not (has_motor_signal and has_start_signal)

        has_overload = re.search(r"\bOVERLOAD\b|\bOVER_LOAD\b", upper) is not None
        mc4_passed = (not has_overload_signal) or has_overload

        return [
            R(
                "MC-1",
                "E-Stop or overload must de-energize motor output",
                mc1_passed,
                "No evidence that safety trip conditions force motor output FALSE",
            ),
            R(
                "MC-2",
                "Motor start should check Stop, E-Stop, and fault conditions",
                mc2_passed,
                "Start_PB condition does not appear to include safety interlocks",
            ),
            R(
                "MC-3",
                "Fault latch should prevent automatic motor restart",
                mc3_passed,
                "No fault latch variable found",
            ),
            R(
                "MC-4",
                "Thermal overload condition should be monitored when provided",
                mc4_passed,
                "No overload input handling found",
            ),
        ]


class TrafficControlValidator(DomainValidator):
    domain_id = "traffic_control"
    domain_name = "Traffic Control"
    rule_prefix = "TC"

    def detect(self, signal_names: set[str], source: str, plan_domain: str) -> bool:
        name_set = {n.upper() for n in signal_names}
        has_red = any("RED" in n for n in name_set)
        has_green = any("GREEN" in n for n in name_set)
        domain_match = "traffic" in plan_domain.lower()
        return (has_red and has_green) or domain_match

    def validate(self, source: str, signal_names: set[str]) -> list[ValidationSafetyResult]:
        upper = source.upper()
        lines = source.splitlines()
        name_set = {n.upper() for n in signal_names}
        has_green_signal = any("GREEN" in n for n in name_set)
        has_amber_signal = any("AMBER" in n or "YELLOW" in n for n in name_set)
        R = self._rule

        has_phases = re.search(r"\bCASE\b", upper) is not None
        has_red_phase = re.search(r"\bRED_LIGHT\b|\bRED\b", upper) is not None

        conflict = False
        for idx, line in enumerate(lines):
            if "GREEN_LIGHT" in line.upper() and ":= TRUE" in line.upper():
                context = " ".join(lines[max(0, idx - 2) : idx + 3]).upper()
                if "AMBER_LIGHT" in context and ":= TRUE" in context:
                    conflict = True
                    break

        has_timers = re.search(r"\bTON\b|\bTIMER\b|\b_TIMER\b", upper) is not None
        conflict_rule_needed = has_green_signal and has_amber_signal

        return [
            R(
                "TC-1",
                "Traffic control should use a phase state machine",
                has_phases,
                "No CASE state machine for phase control found",
            ),
            R(
                "TC-2",
                "Red stop phase must be defined as safe fallback",
                has_red_phase,
                "No Red light output found",
            ),
            R(
                "TC-3",
                "Green and Amber lights must not be active simultaneously",
                (not conflict) if conflict_rule_needed else True,
                "Green and Amber both set TRUE in same code context",
            ),
            R(
                "TC-4",
                "Phase transitions should use timers",
                has_timers or not has_phases,
                "No timer (TON) found for phase timing",
            ),
        ]


class ProcessControlValidator(DomainValidator):
    domain_id = "process_control"
    domain_name = "Process Control"
    rule_prefix = "PC"

    def detect(self, signal_names: set[str], source: str, plan_domain: str) -> bool:
        name_set = {n.upper() for n in signal_names}
        has_level = any("LEVEL" in n or "HIGH" in n or "LOW" in n for n in name_set)
        has_pump = any("PUMP" in n or "VALVE" in n for n in name_set)
        domain_match = any(token in plan_domain.lower() for token in ["process", "level", "tank", "pump"])
        return (has_level and has_pump) or domain_match

    def validate(self, source: str, signal_names: set[str]) -> list[ValidationSafetyResult]:
        upper = source.upper()
        name_set = {n.upper() for n in signal_names}
        has_high_signal = any("HIGH_LEVEL" in n or "HIGH" in n for n in name_set)
        has_estop_signal = any("E_STOP" in n or "EMERGENCY" in n for n in name_set)
        R = self._rule

        has_high_stop = re.search(
            r"HIGH_LEVEL.{0,80}:=\s*FALSE|HIGH_LEVEL.{0,80}END_IF",
            upper,
            re.DOTALL,
        ) is not None
        has_overflow = re.search(r"\bHIGH_HIGH\b|\bOVERFLOW\b|\bHIGH_ALARM\b", upper) is not None
        has_estop_guard = re.search(r"(?:E_STOP|EMERGENCY).{0,120}:=\s*FALSE", upper, re.DOTALL) is not None

        return [
            R(
                "PC-1",
                "High level sensor should stop fill pump/valve",
                has_high_stop or not has_high_signal,
                "No evidence that High_Level stops filling",
            ),
            R(
                "PC-2",
                "Overflow/high-high alarm protection is recommended",
                has_overflow or not has_high_signal,
                "No overflow or high-high alarm handling found",
            ),
            R(
                "PC-3",
                "Emergency stop must de-energize actuators when E-Stop is defined",
                has_estop_guard or not has_estop_signal,
                "No evidence that E-Stop de-energizes pumps/valves",
            ),
        ]


class SafetyInterlockValidator(DomainValidator):
    domain_id = "safety_interlock"
    domain_name = "Safety Interlock"
    rule_prefix = "SI"

    def detect(self, signal_names: set[str], source: str, plan_domain: str) -> bool:
        name_set = {n.upper() for n in signal_names}
        has_interlock = any(
            keyword in n
            for n in name_set
            for keyword in ["INTERLOCK", "PERMISSIVE", "ENABLE", "GUARD"]
        )
        domain_match = "interlock" in plan_domain.lower() or "safety" in plan_domain.lower()
        return has_interlock or domain_match

    def validate(self, source: str, signal_names: set[str]) -> list[ValidationSafetyResult]:
        upper = source.upper()
        R = self._rule
        output_names = [
            n
            for n in signal_names
            if any(keyword in n.upper() for keyword in ["OUTPUT", "VALVE", "MOTOR", "PUMP", "ENABLE"])
        ]

        has_and_chain = re.search(r"\w+\s+AND\s+\w+\s+AND\s+\w+", upper) is not None
        has_gated = len(output_names) == 0 or re.search(
            r"(?:PERMISSIVE|INTERLOCK|ENABLE|ALL_OK).{0,80}:=\s*\w+",
            upper,
            re.DOTALL,
        ) is not None
        has_estop = re.search(r"\bEMERGENCY\b|\bE_STOP\b|\bSTOP\b", upper) is not None

        return [
            R(
                "SI-1",
                "Safety interlock should use multi-condition AND-chain permissive logic",
                has_and_chain,
                "No multi-condition AND chain found for permissive interlocking",
            ),
            R(
                "SI-2",
                "Process outputs should be gated through permissive conditions",
                has_gated,
                "Outputs do not appear to be gated through a permissive variable",
            ),
            R(
                "SI-3",
                "Emergency stop should override all other conditions when available",
                has_estop or len(output_names) == 0,
                "No emergency stop input found in interlock logic",
            ),
        ]


class GenericValidator(DomainValidator):
    domain_id = "generic"
    domain_name = "Generic PLC"
    rule_prefix = "GEN"

    def detect(self, signal_names: set[str], source: str, plan_domain: str) -> bool:
        return True

    def validate(self, source: str, signal_names: set[str]) -> list[ValidationSafetyResult]:
        # Comments and strings must not count as code (P1-01).
        source = strip_comments_and_strings(source)
        upper = source.upper()
        R = self._rule
        has_program = "PROGRAM" in upper and "END_PROGRAM" in upper
        results = [
            R(
                "GEN-1",
                "PROGRAM/END_PROGRAM structure must be present",
                has_program,
                "Missing PROGRAM or END_PROGRAM declaration",
            )
        ]

        # Every block header counts, not only a bare VAR (the GEN-2 half of C-01).
        var_count = len(
            re.findall(r"\b(?:VAR|VAR_INPUT|VAR_OUTPUT|VAR_IN_OUT|VAR_TEMP|VAR_GLOBAL|VAR_EXTERNAL)\b", source, re.IGNORECASE)
        )
        endvar_count = len(re.findall(r"\bEND_VAR\b", source, re.IGNORECASE))
        results.append(
            R(
                "GEN-2",
                "VAR and END_VAR blocks must be balanced",
                var_count == endvar_count,
                f"Mismatched variable blocks: {var_count} VAR/VAR_INPUT/VAR_OUTPUT header(s) vs {endvar_count} END_VAR",
            )
        )

        safety_names = [
            n
            for n in signal_names
            if any(keyword in n.upper() for keyword in ["STOP", "FAULT", "ABORT", "EMERGENCY", "SAFE"])
        ]
        output_names = [
            n
            for n in signal_names
            if any(keyword in n.upper() for keyword in ["VALVE", "MOTOR", "PUMP", "HEATER", "OUTPUT", "RUN"])
        ]
        has_guard = (
            not safety_names
            or not output_names
            or re.search(
                r"(?:"
                + "|".join(re.escape(s.upper()) for s in safety_names[:3])
                + r").{0,200}:=\s*FALSE",
                upper,
                re.DOTALL,
            )
            is not None
        )
        results.append(
            R(
                "GEN-3",
                "Safety inputs should de-energize outputs when active",
                has_guard,
                "No evidence that safety inputs set outputs FALSE",
            )
        )

        if_count = len(re.findall(r"\bIF\b", source, re.IGNORECASE))
        endif_count = len(re.findall(r"\bEND_IF\b", source, re.IGNORECASE))
        results.append(
            R(
                "GEN-4",
                "IF and END_IF must be balanced",
                if_count == endif_count,
                f"Mismatched IF/END_IF: {if_count} IF vs {endif_count} END_IF",
            )
        )

        return results


class ValidationAgent:
    DOMAIN_VALIDATORS: list[DomainValidator] = [
        SequentialBatchValidator(),
        MotorControlValidator(),
        TrafficControlValidator(),
        ProcessControlValidator(),
        SafetyInterlockValidator(),
        GenericValidator(),
    ]

    def __init__(self, mode: ValidationMode = "static", matiec_validator: MatiecValidator | None = None) -> None:
        self.mode = mode
        self.matiec_validator = matiec_validator or MatiecValidator()
        self.plcverif_validator = PLCVerifValidator()
        self.parser_check = ParserCheck()

    def validate(
        self,
        *,
        project_id: str,
        artifact: CodeArtifact,
        plan: PlanObject,
    ) -> ValidationReport:
        if self.mode == "formal":
            return self._validate_formal(project_id=project_id, artifact=artifact, plan=plan)
        if self.mode != "static":
            raise ValueError(f"Unsupported ValidationAgent mode: {self.mode}")

        return self._validate_static(project_id=project_id, artifact=artifact, plan=plan)

    async def validate_in_thread(
        self,
        *,
        project_id: str,
        artifact: CodeArtifact,
        plan: PlanObject,
    ) -> ValidationReport:
        """Runs validate() in a worker thread so a slow MATIEC compile does not block the event loop (D-030)."""
        return await asyncio.to_thread(self.validate, project_id=project_id, artifact=artifact, plan=plan)

    def _validate_static(self, *, project_id: str, artifact: CodeArtifact, plan: PlanObject) -> ValidationReport:
        syntax_errors, validator_used = self._syntax_errors_with_optional_matiec(artifact.source)
        names = {signal.name for signal in [*plan.inputs, *plan.outputs]}
        plan_domain = getattr(plan, "domain", "") or ""
        domain_validator = self._detect_domain_validator(artifact.source, names, plan_domain)
        logger.info(
            "[ValidationAgent] Domain detected: %s — applying %s rules",
            domain_validator.domain_name,
            domain_validator.rule_prefix,
        )
        safety_results = [] if syntax_errors else domain_validator.validate(artifact.source, names)
        failed_safety = [result for result in safety_results if result.status == "failed"]
        formal_errors = [result.details or result.description for result in failed_safety]
        validator_label = "matiec" if validator_used == "matiec" else PARSER_CHECK_LABEL

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
            validator=validator_label,
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

    def _validate_formal(self, *, project_id: str, artifact: CodeArtifact, plan: PlanObject) -> ValidationReport:
        syntax_result = self._run_matiec_syntax(artifact.source)
        syntax_errors = list(syntax_result.get("errors", []))
        if not syntax_result.get("passed", False):
            return ValidationReport(
                projectId=project_id,
                artifactId=artifact.artifactId,
                iteration=artifact.iteration,
                status="SYNTAX_ERROR",
                syntaxPassed=False,
                formalPassed=False,
                solver="matiec.v1",
                validator="matiec.v1",
                checkedAt=self._utc_now(),
                summary="Structured Text syntax validation failed before formal checks.",
                syntaxErrors=syntax_errors,
                formalErrors=[],
                safetyResults=[],
                properties=[],
                errors=syntax_errors,
                counterexample=None,
                counterexamples=[],
            )

        requested_properties = self._requested_properties(plan)
        transpile_result = StToSmvTranspiler().transpile(artifact.source, requested_properties)
        if not transpile_result.success:
            if transpile_result.error and transpile_result.error.startswith("TRANSPILER_UNSUPPORTED"):
                logger.warning(
                    "Formal validation fallback to static checks due to unsupported transpiler construct: %s",
                    transpile_result.unsupported_construct,
                )
                fallback_report = self._validate_static(project_id=project_id, artifact=artifact, plan=plan)
                fallback_summary = (
                    f"{fallback_report.summary} Formal path fell back to static checks because the transpiler "
                    f"does not support: {transpile_result.unsupported_construct}."
                )
                return fallback_report.model_copy(update={"summary": fallback_summary})

            transpile_error = transpile_result.error or "ST to SMV transpilation failed."
            return ValidationReport(
                projectId=project_id,
                artifactId=artifact.artifactId,
                iteration=artifact.iteration,
                status="FORMAL_VIOLATION",
                syntaxPassed=True,
                formalPassed=False,
                solver="matiec+plcverif.v1",
                validator="formal.v1",
                checkedAt=self._utc_now(),
                summary="Structured Text syntax passed, but formal preprocessing failed.",
                syntaxErrors=[],
                formalErrors=[transpile_error],
                safetyResults=[],
                properties=[],
                errors=[transpile_error],
                counterexample=None,
                counterexamples=[],
            )

        formal_result = self._run_coroutine_sync(
            self.plcverif_validator.validate_formal(transpile_result.smv_model or "", requested_properties)
        )
        classification = str(formal_result.get("classification", "FORMAL_VIOLATION")).upper()
        if classification == "TIMEOUT":
            status = "TIMEOUT"
        elif formal_result.get("all_passed", False):
            status = "VERIFIED"
        else:
            status = "FORMAL_VIOLATION"

        property_results = list(formal_result.get("property_results", []))
        safety_results = self._formal_safety_results(property_results, requested_properties)
        formal_errors = list(formal_result.get("errors", []))
        counterexamples = self._formal_counterexamples(formal_result.get("counterexample"))
        properties = [
            ValidationProperty(id=result.id, description=result.description, status=result.status)
            for result in safety_results
        ]

        summary = (
            "Formal validation passed for all requested properties."
            if status == "VERIFIED"
            else "Formal validation reported property violations."
        )
        if status == "TIMEOUT":
            summary = "Formal validation timed out before completion."

        return ValidationReport(
            projectId=project_id,
            artifactId=artifact.artifactId,
            iteration=artifact.iteration,
            status=status,
            syntaxPassed=True,
            formalPassed=status == "VERIFIED",
            solver="matiec+plcverif.v1",
            validator="formal.v1",
            checkedAt=self._utc_now(),
            summary=summary,
            syntaxErrors=[],
            formalErrors=formal_errors,
            safetyResults=safety_results,
            properties=properties,
            errors=formal_errors,
            counterexample=counterexamples or None,
            counterexamples=counterexamples,
        )

    def _syntax_errors_with_optional_matiec(self, st_code: str) -> tuple[list[str], str]:
        """
        Returns (syntax_errors, validator_used).
        Tries MATIEC first and falls back to the parser check (parser.v1) if MATIEC is unavailable.
        A parser-check pass is not evidence level L1 (D-029).
        """
        result = self.matiec_validator.validate_syntax_sync(st_code)

        if result.get("method") == "matiec":
            if result.get("passed"):
                logger.info(
                    "[ValidationAgent] MATIEC syntax: PASSED (return_code=%s)",
                    result.get("return_code", 0),
                )
                return [], "matiec"

            matiec_errors = list(result.get("errors", []))
            logger.warning(
                "[ValidationAgent] MATIEC syntax: FAILED - %s error(s)",
                len(matiec_errors),
            )
            return matiec_errors, "matiec"

        logger.warning(
            "[ValidationAgent] MATIEC unavailable (%s). Using the parser check (%s).",
            result.get("reason", "binary not found"),
            PARSER_CHECK_LABEL,
        )
        return self.parser_check.check(st_code), "parser"

    def _safety_results(self, source: str, plan: PlanObject) -> list[ValidationSafetyResult]:
        names = {signal.name for signal in [*plan.inputs, *plan.outputs]}
        plan_domain = getattr(plan, "domain", "") or ""
        return self._check_safety(source, names, plan_domain)

    def _check_safety(
        self,
        source: str,
        signal_names: set[str],
        plan_domain: str = "",
    ) -> list[ValidationSafetyResult]:
        validator = self._detect_domain_validator(source, signal_names, plan_domain)
        logger.info(
            "[ValidationAgent] Domain detected: %s — applying %s rules",
            validator.domain_name,
            validator.rule_prefix,
        )
        return validator.validate(source, signal_names)

    def _detect_domain_validator(
        self,
        source: str,
        signal_names: set[str],
        plan_domain: str = "",
    ) -> DomainValidator:
        for validator in self.DOMAIN_VALIDATORS:
            if validator.detect(signal_names, source, plan_domain):
                return validator
        return GenericValidator()

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
    def _requested_properties(plan: PlanObject) -> list[str]:
        properties = [*plan.safetyConstraints, *plan.logicRules]
        unique = [value.strip() for value in properties if value.strip()]
        deduped = list(dict.fromkeys(unique))
        return deduped or ["Safety constraints should remain satisfied."]

    @staticmethod
    def _formal_safety_results(
        property_results: list[dict],
        fallback_properties: list[str],
    ) -> list[ValidationSafetyResult]:
        results: list[ValidationSafetyResult] = []
        rows = property_results or [{"property": p, "passed": False, "message": f"No verifier output for: {p}"} for p in fallback_properties]
        for index, row in enumerate(rows, start=1):
            prop = str(row.get("property", f"Property {index}"))
            passed = bool(row.get("passed", False))
            results.append(
                ValidationSafetyResult(
                    id=f"FM-{index}",
                    description=prop,
                    status="passed" if passed else "failed",
                    details=None if passed else str(row.get("message", prop)),
                )
            )
        return results

    @staticmethod
    def _formal_counterexamples(counterexample: object) -> list[dict[str, bool | int | float | str]]:
        if counterexample is None:
            return []
        if isinstance(counterexample, list):
            normalized = [item for item in counterexample if isinstance(item, dict)]
            return normalized
        return [{"step": 1, "trace": str(counterexample)}]

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

    def _run_matiec_syntax(self, source: str) -> dict:
        """Formal mode needs a real compile: a missing MATIEC fails closed with its reason."""
        result = self.matiec_validator.validate_syntax_sync(source)
        if result.get("method") == "unavailable":
            reason = result.get("reason", "binary not found")
            return {"passed": False, "errors": [f"MATIEC unavailable: {reason}"], "raw_output": ""}
        return result

    @staticmethod
    def _run_coroutine_sync(coro):
        try:
            asyncio.get_running_loop()
            running = True
        except RuntimeError:
            running = False

        if not running:
            return asyncio.run(coro)

        result: dict | None = None
        error: Exception | None = None

        def _worker() -> None:
            nonlocal result, error
            try:
                result = asyncio.run(coro)
            except Exception as exc:  # pragma: no cover - defensive path
                error = exc

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        thread.join()
        if error is not None:
            raise error
        return result or {"passed": False, "errors": ["MATIEC syntax validation returned no result."], "raw_output": ""}


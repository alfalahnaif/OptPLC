from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from app.schemas.contracts import CodeArtifact, DebuggingReport, DebuggingStatus, PlanObject, ValidationReport

DebuggingMode = Literal["rule_based", "llm"]


class DebuggingAgent:
    def __init__(self, mode: DebuggingMode = "rule_based") -> None:
        self.mode = mode

    def debug(
        self,
        *,
        project_id: str,
        plan: PlanObject,
        artifact: CodeArtifact,
        validation: ValidationReport,
    ) -> DebuggingReport:
        if self.mode == "llm":
            raise NotImplementedError("DebuggingAgent llm mode is reserved for future integration and makes no external calls.")
        if self.mode != "rule_based":
            raise ValueError(f"Unsupported DebuggingAgent mode: {self.mode}")

        if validation.status == "VERIFIED":
            return self._report(
                project_id=project_id,
                artifact=artifact,
                validation=validation,
                status="NOT_REQUIRED",
                error_type="none",
                root_cause_summary="No debugging required because the code is verified.",
                affected_code_region="None",
                patch_advice=["No patch advice is required. Continue to optimization when ready."],
                suggested_regeneration_prompt="No regeneration required; keep the verified Structured Text artifact.",
                counterexample_summary=None,
            )

        if validation.status == "TIMEOUT":
            return self._report(
                project_id=project_id,
                artifact=artifact,
                validation=validation,
                status="CANNOT_DEBUG",
                error_type="verification_timeout",
                root_cause_summary="The validator timed out before producing a concrete syntax or safety failure.",
                affected_code_region="Verification scope",
                patch_advice=[
                    "Reduce code complexity before retrying validation.",
                    "Simplify nested control-flow branches or split the POU into smaller function blocks.",
                    "Limit the formal verification scope to the most safety-critical properties first.",
                ],
                suggested_regeneration_prompt=(
                    "Regenerate a simpler IEC 61131-3 Structured Text implementation with fewer nested branches "
                    "and explicit safety guards, then rerun validation."
                ),
                counterexample_summary=self._counterexample_summary(validation),
            )

        if validation.status == "SYNTAX_ERROR":
            return self._syntax_report(project_id=project_id, plan=plan, artifact=artifact, validation=validation)

        return self._formal_report(project_id=project_id, plan=plan, artifact=artifact, validation=validation)

    def _syntax_report(
        self,
        *,
        project_id: str,
        plan: PlanObject,
        artifact: CodeArtifact,
        validation: ValidationReport,
    ) -> DebuggingReport:
        errors = [*validation.syntaxErrors, *validation.errors]
        normalized = " ".join(errors).lower()

        if "program or function_block" in normalized or "program declaration" in normalized:
            error_type = "missing_program_declaration"
            region = "POU declaration"
            root = "The Structured Text source is missing a valid PROGRAM or FUNCTION_BLOCK declaration."
            advice = [
                "Add a top-level PROGRAM or FUNCTION_BLOCK declaration before variable blocks.",
                "Use a deterministic PLC-safe POU name such as PLC_<project_id>_Controller.",
                "Keep all executable statements inside the declared POU.",
            ]
        elif "end_program" in normalized or "end_function_block" in normalized:
            error_type = "missing_end_pou"
            region = "POU footer"
            root = "The POU declaration is not closed with the matching end block."
            advice = [
                "Add END_PROGRAM for PROGRAM POUs or END_FUNCTION_BLOCK for FUNCTION_BLOCK POUs.",
                "Place the end block after the final executable assignment.",
                "Verify that no executable logic appears after the POU end marker.",
            ]
        elif "var_input" in normalized or "var_output" in normalized or "end_var" in normalized:
            error_type = "invalid_variable_block"
            region = "Variable declarations"
            root = "One or more required variable declaration blocks are missing or not closed."
            advice = [
                "Emit VAR_INPUT and VAR_OUTPUT sections using the PlanObject signals.",
                "Close every VAR, VAR_INPUT, and VAR_OUTPUT block with END_VAR.",
                "Declare local helper variables inside a separate VAR block.",
            ]
        elif "not declared" in normalized:
            error_type = "undeclared_assigned_variable"
            region = "Variable declarations"
            variable = self._extract_quoted(errors) or "the assigned variable"
            root = f"{variable} is assigned in executable logic but is not declared in any VAR block."
            advice = [
                f"Declare {variable} in VAR_OUTPUT if it is a physical output or VAR if it is internal state.",
                "Ensure assigned variable names match PlanObject output names exactly.",
                "Avoid inventing helper variables without declaring their IEC type.",
            ]
        elif "if statements" in normalized or "case statements" in normalized or "for loops" in normalized or "while loops" in normalized:
            error_type = "unbalanced_control_flow"
            region = "Control-flow block"
            root = "A Structured Text control-flow block is not closed with the matching END_* token."
            advice = [
                "Close IF blocks with END_IF, CASE blocks with END_CASE, FOR blocks with END_FOR, and WHILE blocks with END_WHILE.",
                "Prefer one safety decision per IF block until validation passes.",
                "Regenerate with indentation aligned to block nesting to make closure obvious.",
            ]
        elif "not supported" in normalized or "python" in normalized or "javascript" in normalized or "c++" in normalized:
            error_type = "unsupported_language_syntax"
            region = "Executable logic"
            root = "The artifact contains syntax from a language other than IEC 61131-3 Structured Text."
            advice = [
                "Remove Python, JavaScript, C++, or pseudocode constructs.",
                "Use IEC Structured Text assignments with := and BOOL constants TRUE/FALSE.",
                "Represent all control flow with IF, CASE, FOR, or WHILE blocks.",
            ]
        else:
            error_type = "syntax_error"
            region = "Structured Text source"
            root = "The static validator found IEC Structured Text syntax issues."
            advice = [
                "Review syntaxErrors from the ValidationReport and regenerate the affected POU region.",
                "Keep all PlanObject signals declared with supported IEC types.",
                "Use := for assignments and close every declaration/control block explicitly.",
            ]

        prompt = (
            f"Regenerate IEC 61131-3 Structured Text for project {project_id}. Fix {error_type} in {region}. "
            f"Preserve PlanObject semantics for {self._domain_hint(plan)} and apply this correction: {advice[0]}"
        )
        return self._report(
            project_id=project_id,
            artifact=artifact,
            validation=validation,
            status="PATCH_ADVICE_GENERATED",
            error_type=error_type,
            root_cause_summary=root,
            affected_code_region=region,
            patch_advice=advice,
            suggested_regeneration_prompt=prompt,
            counterexample_summary=self._counterexample_summary(validation),
        )

    def _formal_report(
        self,
        *,
        project_id: str,
        plan: PlanObject,
        artifact: CodeArtifact,
        validation: ValidationReport,
    ) -> DebuggingReport:
        failed_ids = {result.id for result in validation.safetyResults if result.status == "failed"}
        text = " ".join([*validation.formalErrors, *[result.description for result in validation.safetyResults if result.status == "failed"]]).lower()
        signal_names = {signal.name for signal in [*plan.inputs, *plan.outputs]}

        if failed_ids & {"MC-1", "MC-2"} or "emergency stop" in text or "overload" in text:
            error_type = "motor_safety_shutdown"
            region = "Motor_Run and safety latch logic"
            root = "Motor_Run is not visibly forced FALSE by the emergency stop or overload safety path."
            advice = [
                "Introduce a Safety_OK expression using E_Stop and Overload.",
                "Force Run_Cmd and Motor_Run FALSE whenever Safety_OK is false.",
                "Latch Fault_State on E_Stop or Overload and map Fault_Lamp to that latch.",
            ]
        elif failed_ids & {"MC-3"} or "auto-restart" in text or "reset" in text:
            error_type = "unsafe_auto_restart"
            region = "Fault reset and run latch logic"
            root = "The motor can restart without explicit operator reset after a safety trip."
            advice = [
                "Add a latched Fault_State that survives E_Stop recovery.",
                "Clear Fault_State only when Reset_PB is pressed and all safety sources are healthy.",
                "Gate Start_PB and Motor_Run with NOT Fault_State.",
            ]
        elif failed_ids & {"TL-1"} or {"Red_Light", "Green_Light", "Ped_Walk"}.issubset(signal_names):
            error_type = "traffic_conflicting_green"
            region = "Traffic phase output assignments"
            root = "The traffic controller can energize conflicting vehicle green and pedestrian walk signals."
            advice = [
                "Derive Green_Light from NOT Red_Light AND NOT Amber_Light.",
                "Permit Ped_Walk only during a protected red vehicle phase.",
                "Add an emergency or default phase that forces a deterministic non-conflicting lamp pattern.",
            ]
        elif failed_ids & {"TK-1", "TK-2", "TK-3"} or {"Level_PV", "Inlet_Valve"}.issubset(signal_names):
            error_type = "tank_level_safety"
            region = "Tank level limit and valve logic"
            root = "The tank level logic does not fully protect high/low level conditions or REAL setpoint handling."
            advice = [
                "Use REAL declarations for Level_PV, Low_SP, High_SP, and HighHigh_SP.",
                "Close Inlet_Valve when Level_PV reaches High_SP or HighHigh_SP.",
                "Handle Low_SP explicitly before fill requests and keep Outlet_Valve safe by default.",
            ]
        elif failed_ids & {"SI-1", "SI-2"} or {"Machine_Enable", "Trip_Lamp"}.issubset(signal_names):
            error_type = "safety_interlock_fail_safe"
            region = "Permissive and Machine_Enable logic"
            root = "Unsafe interlock conditions do not reliably force the actuator enable output FALSE."
            advice = [
                "Build a Permissive_OK expression from all guard, two-hand, and fault inputs.",
                "Latch Trip_State whenever Permissive_OK is false.",
                "Assign Machine_Enable := Permissive_OK AND NOT Trip_State.",
            ]
        elif failed_ids & {"BT-1", "BT-2", "BT-3"} or {"Start_Batch", "Fill_Valve"}.issubset(signal_names):
            error_type = "batch_state_machine_safety"
            region = "Batch Step state machine"
            root = "The batch sequence is missing safe state, abort, or invalid-step behavior."
            advice = [
                "Declare Step as an INT internal variable and drive sequence outputs from CASE Step OF.",
                "Force Step := 0 on Stop_Batch, abort, or emergency stop.",
                "Add an ELSE branch in CASE Step OF that returns Step to 0 and de-energizes outputs.",
            ]
        else:
            error_type = "formal_violation"
            region = "Safety control logic"
            root = "The validator found a safety property violation in the generated Structured Text."
            advice = [
                "Inspect failed safetyResults and gate the affected output with explicit safe-state conditions.",
                "Introduce a latched fault or permissive state when the property requires memory.",
                "Regenerate the affected logic while preserving the PlanObject I/O contract.",
            ]

        prompt = (
            f"Regenerate IEC 61131-3 Structured Text for project {project_id}. Resolve {error_type} in {region}. "
            f"Keep the existing PlanObject I/O names and apply patch advice: {' '.join(advice)}"
        )
        return self._report(
            project_id=project_id,
            artifact=artifact,
            validation=validation,
            status="PATCH_ADVICE_GENERATED",
            error_type=error_type,
            root_cause_summary=root,
            affected_code_region=region,
            patch_advice=advice,
            suggested_regeneration_prompt=prompt,
            counterexample_summary=self._counterexample_summary(validation),
        )

    @staticmethod
    def _report(
        *,
        project_id: str,
        artifact: CodeArtifact,
        validation: ValidationReport,
        status: DebuggingStatus,
        error_type: str,
        root_cause_summary: str,
        affected_code_region: str,
        patch_advice: list[str],
        suggested_regeneration_prompt: str,
        counterexample_summary: str | None,
    ) -> DebuggingReport:
        return DebuggingReport(
            projectId=project_id,
            sourceArtifactId=artifact.artifactId,
            status=status,
            sourceValidationStatus=validation.status,
            errorType=error_type,
            rootCause=root_cause_summary,
            rootCauseSummary=root_cause_summary,
            affectedCodeRegion=affected_code_region,
            patchAdvice=patch_advice,
            suggestedRegenerationPrompt=suggested_regeneration_prompt,
            counterexampleSummary=counterexample_summary,
            createdAt=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            debugger="rule_based.v1",
            regeneratedArtifactId=None,
        )

    @staticmethod
    def _counterexample_summary(validation: ValidationReport) -> str | None:
        examples = validation.counterexamples or validation.counterexample or []
        if not examples:
            return None
        first = examples[0]
        violation = first.get("violation") or first.get("property") or "safety property"
        return f"{len(examples)} counterexample step(s) reported; first violation: {violation}."

    @staticmethod
    def _extract_quoted(errors: list[str]) -> str | None:
        for error in errors:
            if "'" in error:
                parts = error.split("'")
                if len(parts) >= 3:
                    return parts[1]
        return None

    @staticmethod
    def _domain_hint(plan: PlanObject) -> str:
        names = {signal.name for signal in [*plan.inputs, *plan.outputs]}
        if "Motor_Run" in names:
            return "motor control"
        if "Green_Light" in names:
            return "traffic light control"
        if "Inlet_Valve" in names:
            return "tank level control"
        if "Machine_Enable" in names:
            return "safety interlock"
        if "Fill_Valve" in names:
            return "sequential batch control"
        return "generic PLC control"

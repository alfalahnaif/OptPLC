from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal

from app.schemas.contracts import CodeArtifact, DebuggingReport, DebuggingStatus, PlanObject, ValidationReport

DebuggingMode = Literal["rule_based", "llm"]
logger = logging.getLogger(__name__)

DEBUGGING_SYSTEM_PROMPT = """You are an expert IEC 61131-3 PLC debugging agent.
A formal or static validator found a safety property violation in generated
Structured Text code. Your task is to analyze the violation and produce a
precise, targeted patch directive.

OUTPUT FORMAT: Return ONLY valid JSON - no prose, no markdown fences.
Schema:
{
  "rootCause": str,           (ONE sentence, max 25 words: what logic error caused this)
  "affectedRegion": str,      (which section: "Safety control logic" | "State transitions" | "Output assignments" | "Fault handling")
  "patchAdvice": [str],       (EXACTLY 3 actionable directives, each max 20 words)
  "doNotChange": [str],       (variable/section names that must NOT be touched)
  "suggestedRegenerationPrompt": str,  (full prompt for CodeGenAgent, max 80 words)
  "confidence": "high" | "medium" | "low"
}

ANALYSIS APPROACH:
1. Read the counterexample: what were the exact variable values when the violation occurred?
2. Trace backward: which assignments led to that state?
3. Identify the root cause: missing guard? incorrect latch? wrong operator precedence? scan ordering?
4. Write patch advice that is SPECIFIC to this violation - never generic.
5. The suggestedRegenerationPrompt must tell CodeGenAgent exactly what to fix.

COMMON VIOLATION PATTERNS AND THEIR FIXES:
- "Generic fallback must gate process enable" -> Add Fault_State guard to CASE ELSE branch and all output assignments
- "outputs not FALSE when Emergency_Stop active" -> Move safety force-off AFTER CASE statement (scan ordering bug)
- "motor runs after fault without Reset_PB" -> Add NOT Fault_State condition to run latch
- "mutual exclusion violated" -> Add IF NOT (A) THEN B check before setting B := TRUE
- "no auto-restart after fault" -> Fault_State must latch and require explicit Reset_PB to clear

RULES:
- patchAdvice[0]: the primary code change needed
- patchAdvice[1]: secondary change or constraint to preserve
- patchAdvice[2]: verification hint (what to check after fix)
- doNotChange: always include E-Stop/safety input variable names
- If violation involves scan ordering: explicitly state "move X block AFTER Y block"
- If violation involves missing guard: explicitly name the variable and condition"""


class DebuggingAgent:
    def __init__(self, mode: DebuggingMode = "rule_based") -> None:
        self.mode = mode

    async def debug(
        self,
        *,
        project_id: str,
        plan: PlanObject,
        artifact: CodeArtifact,
        validation: ValidationReport,
        iteration: int = 1,
    ) -> DebuggingReport:
        if self.mode == "llm":
            return await self._debug_with_llm(
                project_id=project_id,
                plan=plan,
                artifact=artifact,
                validation=validation,
                iteration=iteration,
            )
        if self.mode != "rule_based":
            raise ValueError(f"Unsupported DebuggingAgent mode: {self.mode}")

        return self._generate_rule_based(
            project_id=project_id,
            plan=plan,
            artifact=artifact,
            validation=validation,
        )

    def _generate_rule_based(
        self,
        *,
        project_id: str,
        plan: PlanObject,
        artifact: CodeArtifact,
        validation: ValidationReport,
    ) -> DebuggingReport:
        if validation.status == "CHECKS_PASSED":
            return self._report(
                project_id=project_id,
                artifact=artifact,
                validation=validation,
                status="NOT_REQUIRED",
                error_type="none",
                root_cause_summary="No debugging required because the validation checks passed.",
                affected_code_region="None",
                patch_advice=["No patch advice is required. Continue to optimization when ready."],
                suggested_regeneration_prompt="No regeneration required; keep the current Structured Text artifact.",
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

    async def _debug_with_llm(
        self,
        project_id: str,
        plan: PlanObject,
        artifact: CodeArtifact,
        validation: ValidationReport,
        iteration: int = 1,
    ) -> DebuggingReport:
        from app.agents.llm_client import llm_complete
        import json
        import re

        status = getattr(validation, "status", "FORMAL_VIOLATION")
        violation_summary = ""
        counterexample_text = ""

        if hasattr(validation, "safetyResults") and validation.safetyResults:
            failed = [result for result in validation.safetyResults if getattr(result, "status", "") == "failed"]
            if failed:
                violation_summary = f"Failed safety checks ({len(failed)}/{len(validation.safetyResults)}):\n"
                for result in failed:
                    desc = getattr(result, "description", str(result))
                    details = getattr(result, "details", "")
                    violation_summary += f"  - {desc}"
                    if details:
                        violation_summary += f": {details}"
                    violation_summary += "\n"

        if hasattr(validation, "counterexample") and validation.counterexample:
            ce = validation.counterexample
            if isinstance(ce, dict):
                counterexample_text = json.dumps(ce, indent=2)[:1500]
            else:
                counterexample_text = str(ce)[:1500]

        if hasattr(validation, "syntaxErrors") and validation.syntaxErrors:
            violation_summary += "Syntax errors:\n"
            for err in validation.syntaxErrors[:5]:
                violation_summary += f"  - {err}\n"

        plan_summary = ""
        if plan:
            inputs = [getattr(signal, "name", str(signal)) for signal in getattr(plan, "inputs", [])]
            outputs = [getattr(signal, "name", str(signal)) for signal in getattr(plan, "outputs", [])]
            safety = getattr(plan, "safetyConstraints", [])
            plan_summary = (
                f"Inputs: {', '.join(inputs)}\n"
                f"Outputs: {', '.join(outputs)}\n"
                "Safety constraints:\n" + "\n".join(f"  - {item}" for item in safety[:5])
            )

        st_code = getattr(artifact, "source", "") or ""
        lines = st_code.splitlines()
        if len(lines) > 80:
            st_code = "\n".join(lines[:80]) + "\n(* ... truncated ... *)"

        iteration_context = ""
        if iteration > 1:
            iteration_context = (
                f"\n\nIMPORTANT: This is repair attempt {iteration}. "
                "Previous patch advice did not resolve the violation. "
                "Provide DIFFERENT, more specific guidance this time. "
                "Focus on the exact line or block causing the issue."
            )

        user_content = f"""PROJECT: {project_id}
VALIDATION STATUS: {status}

VIOLATION DETAILS:
{violation_summary or 'FORMAL_VIOLATION - generic fallback safety check failed'}

COUNTEREXAMPLE (variable states at violation):
{counterexample_text or 'No counterexample available - check static safety rules'}

PLAN REQUIREMENTS:
{plan_summary}

CURRENT ST CODE:
{st_code}
{iteration_context}

Analyze the violation and provide targeted patch advice."""

        try:
            response = await llm_complete(
                system=DEBUGGING_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
                temperature=0.2,
                max_tokens=600,
            )

            cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", response.content).strip()
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if not match:
                raise ValueError("No JSON object in LLM response")

            data = json.loads(match.group())

            root_cause = data.get("rootCause", "Safety property violation detected")
            patch_advice = data.get("patchAdvice", [])
            if not patch_advice or len(patch_advice) < 1:
                raise ValueError("Empty patchAdvice in response")

            while len(patch_advice) < 3:
                patch_advice.append("Revalidate after applying the above changes.")
            patch_advice = patch_advice[:3]

            affected_region = data.get("affectedRegion", "Safety control logic")
            regen_prompt = data.get("suggestedRegenerationPrompt", "")
            if not regen_prompt:
                regen_prompt = (
                    f"Regenerate IEC 61131-3 Structured Text for project {project_id}. "
                    f"Resolve {status} in {affected_region}. "
                    "Keep the existing PlanObject I/O names and apply patch advice: "
                    f"{' '.join(patch_advice)}"
                )

            logger.info(
                f"[DebuggingAgent/llm.v1] project={project_id} "
                f"root_cause='{root_cause[:60]}' "
                f"tokens={response.input_tokens + response.output_tokens}"
            )

            return self._report(
                project_id=project_id,
                artifact=artifact,
                validation=validation,
                status="PATCH_ADVICE_GENERATED",
                error_type=("syntax_error" if status == "SYNTAX_ERROR" else "formal_violation"),
                root_cause_summary=root_cause,
                affected_code_region=affected_region,
                patch_advice=patch_advice,
                suggested_regeneration_prompt=regen_prompt,
                counterexample_summary=self._counterexample_summary(validation),
                source_label="llm.v1",
                llm_provider=response.provider,
                llm_model=response.model,
                tokens_used=response.input_tokens + response.output_tokens,
            )
        except Exception as exc:
            logger.warning(f"[DebuggingAgent] LLM mode failed: {exc}. Falling back to rule_based.")
            return self._generate_rule_based(
                project_id=project_id,
                plan=plan,
                artifact=artifact,
                validation=validation,
            )

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
        source_label: str = "rule_based.v1",
        llm_provider: str | None = None,
        llm_model: str | None = None,
        tokens_used: int | None = None,
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
            debugger=source_label,
            regeneratedArtifactId=None,
            llmProvider=llm_provider,
            llmModel=llm_model,
            tokensUsed=tokens_used,
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

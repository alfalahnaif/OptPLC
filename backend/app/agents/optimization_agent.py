from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Callable, Literal

from app.agents.validation_agent import ValidationAgent
from app.schemas.contracts import (
    CodeArtifact,
    CodeMetadata,
    CodeMetrics,
    OptimizationPassResult,
    OptimizationReport,
    OptimizationRollbackEvent,
    PlanObject,
    RepairLoopReport,
    ValidationReport,
)
from app.services.metrics_service import MetricsService

OptimizationMode = Literal["static", "llm"]
logger = logging.getLogger(__name__)

OPT_SYSTEM_BASE = """You are an IEC 61131-3 PLC code optimization agent.

ABSOLUTE CONSTRAINTS — violation triggers immediate rollback:
1. IDENTICAL logical behavior for ALL possible input combinations
2. Do NOT rename VAR_INPUT or VAR_OUTPUT variable names (hardware-fixed)
3. Do NOT add new functionality or new output variables
4. Do NOT change safety guard conditions (Emergency, Fault, interlock)
5. ALL logic MUST resolve in a SINGLE PLC scan cycle:
   - Do NOT create variables that feed back into themselves in same scan
   - Do NOT introduce scan-cycle dependencies not present in original
   - If UNSURE whether a change is scan-safe: LEAVE IT UNCHANGED
IEC 61131-3 TYPE RULES (checked against the pinned MATIEC, D-006):
- AND/OR operators require BOOL operands only
- Never use an INT variable directly in AND/OR expressions
- WRONG: Step_State AND NOT Fault_State
- RIGHT: (Step_State > 0) AND NOT Fault_State
- All CASE labels must be integer literals, not named constants
6. Output ONLY the optimized ST code — no markdown, no explanation"""

PASS_CONFIGS = {
    1: {
        "name": "Structural Simplification",
        "temperature": 0.1,
        "objective": """PASS 1: Structural Simplification
Merge redundant IF/ELSIF chains into minimal form.
Remove dead code (branches that can never execute).
Simplify IF-THEN-ELSE when both branches assign same variable:
  BEFORE: IF A THEN X:=TRUE; ELSE X:=FALSE; END_IF;
  AFTER:  X := A;
Combine consecutive assignments to same variable.
NEVER convert CASE to IF chains — that is reverse optimization.
Target: reduce IF count and line count.""",
    },
    2: {
        "name": "Logic Compaction",
        "temperature": 0.15,
        "objective": """PASS 2: Logic Compaction
Rewrite multi-line boolean IF chains as single assignments.
  BEFORE: IF A AND NOT B THEN C:=TRUE; ELSE C:=FALSE; END_IF;
  AFTER:  C := A AND NOT B;
Apply De Morgan's law where it reduces operator count.
Remove intermediate BOOL variables that mirror another variable.
Only compact when BOTH branches assign the same output variable.""",
    },
    3: {
        "name": "Maintainability Enhancement",
        "temperature": 0.2,
        "objective": """PASS 3: Maintainability Enhancement
1. Rename ambiguous INTERNAL VAR names to self-documenting ones.
   ONLY rename internal VARs. NEVER rename VAR_INPUT or VAR_OUTPUT.
2. Add ONE-LINE comment (* ... *) above each logical section.
3. Reorder logic blocks: safety sensing → fault handling → step transitions → output assignment.
4. Remove intermediate variables that simply mirror NOT of another.
Add comments that explain WHAT the code does, not HOW.""",
    },
}


class OptimizationAgent:
    def __init__(self, mode: OptimizationMode = "static") -> None:
        self.mode = mode

    async def optimize(
        self,
        *,
        project_id: str,
        artifact: CodeArtifact,
        plan: PlanObject,
        validation: ValidationReport,
        repair_loop_report: RepairLoopReport | None = None,
    ) -> OptimizationReport:
        if self.mode == "llm":
            return await self._optimize_with_llm(
                project_id=project_id,
                artifact=artifact,
                plan=plan,
                validation=validation,
                repair_loop_report=repair_loop_report,
            )
        if self.mode != "static":
            raise ValueError(f"Unsupported OptimizationAgent mode: {self.mode}")
        return await self._optimize_static(
            project_id=project_id,
            artifact=artifact,
            plan=plan,
            validation=validation,
            repair_loop_report=repair_loop_report,
        )

    async def _optimize_static(
        self,
        *,
        project_id: str,
        artifact: CodeArtifact,
        plan: PlanObject,
        validation: ValidationReport,
        repair_loop_report: RepairLoopReport | None = None,
    ) -> OptimizationReport:
        original_metrics = MetricsService.calculate(artifact.source)
        if validation.status != "CHECKS_PASSED":
            preserved_artifact = self._optimized_artifact(
                project_id=project_id,
                source_artifact=artifact,
                source=artifact.source,
                iteration=artifact.iteration,
                metrics=original_metrics,
                generator="static_optimizer.v1",
            )
            return OptimizationReport(
                projectId=project_id,
                sourceArtifactId=artifact.artifactId,
                optimizedArtifactId=preserved_artifact.artifactId,
                status="CANNOT_OPTIMIZE",
                optimizer="static.v1",
                originalCode=artifact,
                optimizedCode=preserved_artifact,
                passes=[],
                beforeMetrics=original_metrics,
                afterMetrics=original_metrics,
                metricsDelta=MetricsService.delta(original_metrics, original_metrics),
                revalidationStatus=validation.status,
                rollbackEvents=[],
                createdAt=self._utc_now(),
                summary="Static optimization did not run because the latest validation status is not CHECKS_PASSED.",
                revalidated=False,
            )

        current_source = artifact.source
        passes: list[OptimizationPassResult] = []
        rollback_events: list[OptimizationRollbackEvent] = []
        final_validation = validation
        changed = False

        for index, (name, transform) in enumerate(self._passes(), start=1):
            before_metrics = MetricsService.calculate(current_source)
            candidate_source, summary = transform(current_source, plan)
            candidate_artifact = self._candidate_artifact(
                project_id=project_id,
                source_artifact=artifact,
                source=candidate_source,
                iteration=artifact.iteration,
                candidate_index=index,
            )
            candidate_validation = await ValidationAgent(mode="static").validate_in_thread(
                project_id=project_id,
                artifact=candidate_artifact,
                plan=plan,
            )

            if candidate_validation.status == "CHECKS_PASSED":
                after_metrics = MetricsService.calculate(candidate_source)
                did_change = candidate_source != current_source
                current_source = candidate_source
                final_validation = candidate_validation
                changed = changed or did_change
                passes.append(
                    OptimizationPassResult(
                        name=name,
                        status="applied" if did_change else "no_changes",
                        summary=summary if did_change else f"{summary} No source change was required.",
                        accepted=True,
                        revalidationStatus=candidate_validation.status,
                        beforeMetrics=before_metrics,
                        afterMetrics=after_metrics,
                    )
                )
            else:
                rollback_events.append(
                    OptimizationRollbackEvent(
                        passName=name,
                        reason="Candidate failed static revalidation and was rolled back.",
                        revalidationStatus=candidate_validation.status,
                    )
                )
                passes.append(
                    OptimizationPassResult(
                        name=name,
                        status="rolled_back",
                        summary=f"{summary} Rolled back because revalidation returned {candidate_validation.status}.",
                        accepted=False,
                        revalidationStatus=candidate_validation.status,
                        beforeMetrics=before_metrics,
                        afterMetrics=before_metrics,
                    )
                )

        after_metrics = MetricsService.calculate(current_source)
        optimized_artifact = self._optimized_artifact(
            project_id=project_id,
            source_artifact=artifact,
            source=current_source,
            iteration=artifact.iteration + 1,
            metrics=after_metrics,
            generator="static_optimizer.v1",
        )

        if changed:
            status = "OPTIMIZED"
        elif rollback_events:
            status = "ROLLED_BACK"
        else:
            status = "NO_CHANGES"

        return OptimizationReport(
            projectId=project_id,
            sourceArtifactId=artifact.artifactId,
            optimizedArtifactId=optimized_artifact.artifactId,
            status=status,
            optimizer="static.v1",
            originalCode=artifact,
            optimizedCode=optimized_artifact,
            passes=passes,
            beforeMetrics=original_metrics,
            afterMetrics=after_metrics,
            metricsDelta=MetricsService.delta(original_metrics, after_metrics),
            revalidationStatus=final_validation.status,
            rollbackEvents=rollback_events,
            createdAt=self._utc_now(),
            summary=self._summary(status=status, passes=passes, repair_loop_report=repair_loop_report),
            revalidated=final_validation.status == "CHECKS_PASSED",
        )

    async def _optimize_with_llm(
        self,
        project_id: str,
        artifact: CodeArtifact,
        plan: PlanObject,
        validation: ValidationReport,
        repair_loop_report: RepairLoopReport | None,
    ) -> OptimizationReport:
        from app.agents.llm_client import llm_complete

        current_code = artifact.source
        current_validation = validation
        passes_data: list[OptimizationPassResult] = []
        rollback_events: list[OptimizationRollbackEvent] = []
        passes_applied = 0
        changed = False
        input_names = [signal.name for signal in plan.inputs]
        output_names = [signal.name for signal in plan.outputs]
        safety_constraints = plan.safetyConstraints or []

        for pass_num in range(1, 4):
            cfg = PASS_CONFIGS[pass_num]
            pass_name = str(cfg["name"])
            before_source = current_code
            before_metrics = MetricsService.calculate(before_source)
            system = OPT_SYSTEM_BASE + "\n\n" + str(cfg["objective"])
            user_content = (
                f"PLAN REFERENCE:\n"
                f"Inputs (DO NOT RENAME): {', '.join(input_names)}\n"
                f"Outputs (DO NOT RENAME): {', '.join(output_names)}\n"
                f"Safety constraints: {chr(10).join(safety_constraints)}\n\n"
                f"CURRENT CODE TO OPTIMIZE:\n{before_source}\n\n"
                f"Apply {pass_name} now. Output ONLY the ST code."
            )

            try:
                response = await llm_complete(
                    system=system,
                    messages=[{"role": "user", "content": user_content}],
                    temperature=float(cfg["temperature"]),
                    max_tokens=2000,
                )
                candidate = response.content.strip()
                candidate = re.sub(r"```[\w-]*\s*|\s*```", "", candidate).strip()

                missing_io = [name for name in output_names if name not in candidate]
                if missing_io:
                    passes_data.append(
                        OptimizationPassResult(
                            name=pass_name,
                            status="no_changes",
                            summary=f"{pass_name} skipped: missing output names in candidate {missing_io}.",
                            accepted=False,
                            revalidationStatus=current_validation.status,
                            beforeMetrics=before_metrics,
                            afterMetrics=before_metrics,
                        )
                    )
                    logger.warning("[OptimizationAgent] Pass %s skipped due to missing I/O names: %s", pass_num, missing_io)
                    continue

                if "PROGRAM" not in candidate.upper() or "END_PROGRAM" not in candidate.upper():
                    passes_data.append(
                        OptimizationPassResult(
                            name=pass_name,
                            status="no_changes",
                            summary=f"{pass_name} skipped: candidate does not contain PROGRAM...END_PROGRAM.",
                            accepted=False,
                            revalidationStatus=current_validation.status,
                            beforeMetrics=before_metrics,
                            afterMetrics=before_metrics,
                        )
                    )
                    logger.warning("[OptimizationAgent] Pass %s skipped due to invalid ST structure.", pass_num)
                    continue

                test_artifact = artifact.model_copy(
                    update={
                        "source": candidate,
                        "artifactId": f"{project_id}-optimization-candidate-{pass_num}",
                    }
                )
                recheck = await ValidationAgent(mode="static").validate_in_thread(
                    project_id=project_id,
                    artifact=test_artifact,
                    plan=plan,
                )

                if recheck.status == "CHECKS_PASSED":
                    after_metrics = MetricsService.calculate(candidate)
                    did_change = candidate != before_source
                    current_code = candidate
                    current_validation = recheck
                    changed = changed or did_change
                    if did_change:
                        passes_applied += 1
                    passes_data.append(
                        OptimizationPassResult(
                            name=pass_name,
                            status="applied" if did_change else "no_changes",
                            summary=(
                                f"{pass_name} applied and revalidated."
                                if did_change
                                else f"{pass_name} produced no source changes after normalization; candidate revalidated."
                            ),
                            accepted=True,
                            revalidationStatus=recheck.status,
                            beforeMetrics=before_metrics,
                            afterMetrics=after_metrics,
                        )
                    )
                    logger.info("[OptimizationAgent] Pass %s (%s) APPLIED", pass_num, pass_name)
                else:
                    rollback_events.append(
                        OptimizationRollbackEvent(
                            passName=pass_name,
                            reason=f"Re-validation failed: {recheck.status}. Candidate rolled back to pre-pass code.",
                            revalidationStatus=recheck.status,
                        )
                    )
                    passes_data.append(
                        OptimizationPassResult(
                            name=pass_name,
                            status="rolled_back",
                            summary=f"{pass_name} rolled back because static revalidation returned {recheck.status}.",
                            accepted=False,
                            revalidationStatus=recheck.status,
                            beforeMetrics=before_metrics,
                            afterMetrics=before_metrics,
                        )
                    )
                    logger.warning("[OptimizationAgent] Pass %s ROLLED BACK: %s", pass_num, recheck.status)
            except Exception as exc:
                rollback_events.append(
                    OptimizationRollbackEvent(
                        passName=pass_name,
                        reason=f"Pass failed with exception and was rolled back: {exc}",
                        revalidationStatus=current_validation.status,
                    )
                )
                passes_data.append(
                    OptimizationPassResult(
                        name=pass_name,
                        status="rolled_back",
                        summary=f"{pass_name} rolled back due to pass execution error: {exc}",
                        accepted=False,
                        revalidationStatus=current_validation.status,
                        beforeMetrics=before_metrics,
                        afterMetrics=before_metrics,
                    )
                )
                logger.error("[OptimizationAgent] Pass %s error: %s", pass_num, exc)

        metrics_before = MetricsService.calculate(artifact.source)
        metrics_after = MetricsService.calculate(current_code)
        optimized_artifact = self._optimized_artifact(
            project_id=project_id,
            source_artifact=artifact,
            source=current_code,
            iteration=artifact.iteration + 1,
            metrics=metrics_after,
            generator="OptimizationAgent/llm.v1",
        )
        if changed:
            status = "OPTIMIZED"
        elif rollback_events:
            status = "ROLLED_BACK"
        else:
            status = "NO_CHANGES"
        summary = (
            f"LLM optimizer applied {passes_applied} pass(es) with per-pass revalidation and rollback enforcement."
            if status == "OPTIMIZED"
            else "LLM optimizer made no accepted source changes after revalidation safeguards."
        )
        if status == "ROLLED_BACK":
            summary = "LLM optimizer rolled back one or more passes after failed revalidation; safe baseline was preserved."
        if repair_loop_report and repair_loop_report.finalStatus == "CHECKS_PASSED":
            summary = f"{summary} Optimization ran after the repair loop reached passing checks."

        return OptimizationReport(
            projectId=project_id,
            sourceArtifactId=artifact.artifactId,
            optimizedArtifactId=optimized_artifact.artifactId,
            status=status,
            optimizer="llm.v1",
            originalCode=artifact,
            optimizedCode=optimized_artifact,
            passes=passes_data,
            beforeMetrics=metrics_before,
            afterMetrics=metrics_after,
            metricsDelta=MetricsService.delta(metrics_before, metrics_after),
            revalidationStatus=current_validation.status,
            rollbackEvents=rollback_events,
            createdAt=self._utc_now(),
            summary=summary,
            revalidated=current_validation.status == "CHECKS_PASSED",
        )

    @staticmethod
    def _passes() -> list[tuple[str, Callable[[str, PlanObject], tuple[str, str]]]]:
        return [
            ("Structural Simplification", OptimizationAgent._structural_simplification),
            ("Logic Compaction", OptimizationAgent._logic_compaction),
            ("Maintainability Enhancement", OptimizationAgent._maintainability_enhancement),
        ]

    @staticmethod
    def _structural_simplification(source: str, plan: PlanObject) -> tuple[str, str]:
        optimized = source
        motor_pattern = re.compile(
            r"IF NOT Safety_OK THEN\s+"
            r"Fault_State := TRUE;\s+"
            r"Run_Cmd := FALSE;\s+"
            r"END_IF;\s+"
            r"(?:\(\* Manual reset is required before restart after any safety trip\. \*\)\s+)?"
            r"IF Fault_State AND Reset_PB AND Safety_OK THEN\s+"
            r"Fault_State := FALSE;\s+"
            r"END_IF;",
            flags=re.MULTILINE,
        )
        optimized = motor_pattern.sub(
            "\n".join(
                [
                    "IF NOT Safety_OK THEN",
                    "    Fault_State := TRUE;",
                    "    Run_Cmd := FALSE;",
                    "ELSIF Reset_PB THEN",
                    "    Fault_State := FALSE;",
                    "END_IF;",
                ]
            ),
            optimized,
            count=1,
        )
        optimized = re.sub(r"\n{3,}", "\n\n", optimized)
        return optimized, "Collapsed compatible nested/adjacent safety IF blocks and normalized redundant safety checks."

    @staticmethod
    def _logic_compaction(source: str, plan: PlanObject) -> tuple[str, str]:
        optimized = source
        start_stop_pattern = re.compile(
            r"IF Start_PB AND NOT Stop_PB AND NOT Fault_State THEN\s+"
            r"Run_Cmd := TRUE;\s+"
            r"END_IF;\s+"
            r"IF Stop_PB OR Fault_State THEN\s+"
            r"Run_Cmd := FALSE;\s+"
            r"END_IF;",
            flags=re.MULTILINE,
        )
        optimized = start_stop_pattern.sub(
            "Run_Cmd := (Run_Cmd OR Start_PB) AND NOT Stop_PB AND NOT Fault_State;",
            optimized,
            count=1,
        )
        optimized = OptimizationAgent._remove_consecutive_duplicate_assignments(optimized)
        optimized = re.sub(r"\n{3,}", "\n\n", optimized)
        return optimized, "Compacted repeated latch/reset assignments and removed consecutive duplicate actuator assignments."

    @staticmethod
    def _maintainability_enhancement(source: str, plan: PlanObject) -> tuple[str, str]:
        optimized = source
        if "(* Optimization note:" not in optimized:
            marker = "(* Main control logic. *)"
            note = "(* Optimization note: safety logic is evaluated before normal operation. *)"
            if marker in optimized:
                optimized = optimized.replace(marker, f"{marker}\n{note}", 1)
            else:
                optimized = optimized.replace("VAR_OUTPUT", "(* Optimization note: grouped declarations and deterministic outputs. *)\nVAR_OUTPUT", 1)

        optimized = OptimizationAgent._ensure_safe_case_default(optimized)
        optimized = re.sub(r"\n{3,}", "\n\n", optimized)
        return optimized, "Added deterministic maintainability annotations and ensured safe CASE defaults where state logic exists."

    @staticmethod
    def _remove_consecutive_duplicate_assignments(source: str) -> str:
        lines = source.splitlines()
        deduped: list[str] = []
        previous_assignment = ""
        for line in lines:
            stripped = line.strip()
            if ":=" in stripped and stripped == previous_assignment:
                continue
            deduped.append(line)
            previous_assignment = stripped if ":=" in stripped else ""
        return "\n".join(deduped)

    @staticmethod
    def _ensure_safe_case_default(source: str) -> str:
        if "CASE Step OF" not in source or "END_CASE;" not in source:
            return source
        case_block_match = re.search(r"CASE Step OF(?P<body>.*?)END_CASE;", source, flags=re.DOTALL)
        if not case_block_match or re.search(r"\bELSE\b", case_block_match.group("body"), flags=re.IGNORECASE):
            return source
        replacement = f"CASE Step OF{case_block_match.group('body')}    ELSE\n        Step := 0;\nEND_CASE;"
        return source[: case_block_match.start()] + replacement + source[case_block_match.end() :]

    @staticmethod
    def _candidate_artifact(
        *,
        project_id: str,
        source_artifact: CodeArtifact,
        source: str,
        iteration: int,
        candidate_index: int,
    ) -> CodeArtifact:
        metrics = MetricsService.calculate(source)
        return source_artifact.model_copy(
            update={
                "projectId": project_id,
                "artifactId": f"{project_id}-optimization-candidate-{candidate_index}",
                "source": source,
                "iteration": iteration,
                "metrics": CodeMetrics(
                    loc=metrics.loc,
                    cyclomaticComplexity=metrics.cyclomaticComplexity,
                    maintainabilityIndex=metrics.maintainabilityIndex,
                ),
            }
        )

    @staticmethod
    def _optimized_artifact(
        *,
        project_id: str,
        source_artifact: CodeArtifact,
        source: str,
        iteration: int,
        metrics,
        generator: str,
    ) -> CodeArtifact:
        created_at = OptimizationAgent._utc_now()
        return source_artifact.model_copy(
            update={
                "projectId": project_id,
                "artifactId": f"{project_id}-code-optimized-{iteration}",
                "filename": source_artifact.filename.replace(".st", "_optimized.st"),
                "source": source,
                "iteration": iteration,
                "generatedAt": created_at,
                "metrics": CodeMetrics(
                    loc=metrics.loc,
                    cyclomaticComplexity=metrics.cyclomaticComplexity,
                    maintainabilityIndex=metrics.maintainabilityIndex,
                ),
                "metadata": CodeMetadata(
                    generator=generator,
                    iecStandard="IEC 61131-3",
                    sourcePlanId=source_artifact.metadata.sourcePlanId,
                    createdAt=created_at,
                    iteration=iteration,
                ),
            }
        )

    @staticmethod
    def _summary(
        *,
        status: str,
        passes: list[OptimizationPassResult],
        repair_loop_report: RepairLoopReport | None,
    ) -> str:
        accepted = sum(1 for item in passes if item.accepted and item.status == "applied")
        rolled_back = sum(1 for item in passes if item.status == "rolled_back")
        repair_context = " after the repair loop reached passing checks" if repair_loop_report and repair_loop_report.finalStatus == "CHECKS_PASSED" else ""
        if status == "OPTIMIZED":
            return f"Static optimizer applied {accepted} pass(es){repair_context}; every accepted pass revalidated successfully."
        if status == "NO_CHANGES":
            return "Static optimizer found no safe source changes; the checked code was preserved."
        if status == "ROLLED_BACK":
            return f"Static optimizer rolled back {rolled_back} pass(es) because revalidation failed."
        return "Static optimizer could not run on the current artifact."

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

from __future__ import annotations

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


class OptimizationAgent:
    def __init__(self, mode: OptimizationMode = "static") -> None:
        self.mode = mode

    def optimize(
        self,
        *,
        project_id: str,
        artifact: CodeArtifact,
        plan: PlanObject,
        validation: ValidationReport,
        repair_loop_report: RepairLoopReport | None = None,
    ) -> OptimizationReport:
        if self.mode == "llm":
            raise NotImplementedError("OptimizationAgent llm mode is reserved for future LLM-assisted optimization and makes no external calls.")
        if self.mode != "static":
            raise ValueError(f"Unsupported OptimizationAgent mode: {self.mode}")

        original_metrics = MetricsService.calculate(artifact.source)
        if validation.status != "VERIFIED":
            preserved_artifact = self._optimized_artifact(
                project_id=project_id,
                source_artifact=artifact,
                source=artifact.source,
                iteration=artifact.iteration,
                metrics=original_metrics,
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
                summary="Static optimization did not run because the latest validation status is not VERIFIED.",
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
            candidate_validation = ValidationAgent(mode="static").validate(
                project_id=project_id,
                artifact=candidate_artifact,
                plan=plan,
            )

            if candidate_validation.status == "VERIFIED":
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
            revalidated=final_validation.status == "VERIFIED",
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
                    generator="static_optimizer.v1",
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
        repair_context = " after repair-loop verification" if repair_loop_report and repair_loop_report.finalStatus == "VERIFIED" else ""
        if status == "OPTIMIZED":
            return f"Static optimizer applied {accepted} pass(es){repair_context}; every accepted pass revalidated successfully."
        if status == "NO_CHANGES":
            return "Static optimizer found no safe source changes; verified code was preserved."
        if status == "ROLLED_BACK":
            return f"Static optimizer rolled back {rolled_back} pass(es) because revalidation failed."
        return "Static optimizer could not run on the current artifact."

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

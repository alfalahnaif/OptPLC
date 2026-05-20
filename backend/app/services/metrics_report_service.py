from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.contracts import (
    CodeArtifact,
    MetricsHistoryEntry,
    MetricsReport,
    MetricsReportDelta,
    MetricsSource,
    StructuredTextMetrics,
)
from app.services.metrics_service import MetricsService
from app.storage.memory import MemoryStore


class MetricsReportService:
    def __init__(self, storage: MemoryStore) -> None:
        self.storage = storage

    def get_metrics(self, project_id: str) -> MetricsReport:
        self.storage.require_project(project_id)
        plan = self.storage.get_plan(project_id)
        if plan is None:
            raise ValueError("PlanObject must be generated before metrics can be computed.")

        code_history = self.storage.list_code_artifacts(project_id)
        if not code_history:
            raise ValueError("CodeArtifact must be generated before metrics can be computed.")

        generated_code = code_history[0]
        latest_validation = self.storage.get_validation_report(project_id)
        optimization_report = self.storage.get_optimization_report(project_id)
        repair_loop_report = self.storage.get_repair_loop_report(project_id)

        if optimization_report is not None:
            source = MetricsSource(
                selected="optimized_code",
                generatedCode=generated_code.artifactId,
                repairedCode=repair_loop_report.finalCodeArtifact.artifactId if repair_loop_report else None,
                optimizedCode=optimization_report.optimizedArtifactId,
            )
            before_artifact = optimization_report.originalCode
            after_artifact = optimization_report.optimizedCode
            summary = "Metrics compare the pre-optimization code with the latest optimized Structured Text artifact."
        elif repair_loop_report is not None:
            source = MetricsSource(
                selected="repaired_code",
                generatedCode=generated_code.artifactId,
                repairedCode=repair_loop_report.finalCodeArtifact.artifactId,
                optimizedCode=None,
            )
            before_artifact = generated_code
            after_artifact = repair_loop_report.finalCodeArtifact
            summary = "Metrics compare the original generated code with the repaired and revalidated Structured Text artifact."
        else:
            source = MetricsSource(
                selected="generated_code",
                generatedCode=generated_code.artifactId,
                repairedCode=None,
                optimizedCode=None,
            )
            before_artifact = generated_code
            after_artifact = generated_code
            summary = "Metrics are based on the generated Structured Text artifact; no repair or optimization report exists yet."

        before_metrics = MetricsService.calculate(before_artifact.source)
        after_metrics = MetricsService.calculate(after_artifact.source)
        history = self._history_entries(
            generated_code=generated_code,
            repair_artifact=repair_loop_report.finalCodeArtifact if repair_loop_report else None,
            optimized_artifact=optimization_report.optimizedCode if optimization_report else None,
        )

        report = MetricsReport(
            projectId=project_id,
            source=source,
            beforeMetrics=before_metrics,
            afterMetrics=after_metrics,
            metricsDelta=self._delta(before_metrics, after_metrics),
            history=history,
            latestValidationStatus=latest_validation.status if latest_validation else None,
            latestOptimizationStatus=optimization_report.status if optimization_report else None,
            createdAt=self._utc_now(),
            summary=summary,
        )
        self.storage.save_metrics_report(project_id, report)
        return report

    @staticmethod
    def _history_entries(
        *,
        generated_code: CodeArtifact,
        repair_artifact: CodeArtifact | None,
        optimized_artifact: CodeArtifact | None,
    ) -> list[MetricsHistoryEntry]:
        entries = [
            MetricsReportService._entry("Generated code", "generated_code", generated_code),
        ]
        if repair_artifact is not None and repair_artifact.artifactId != generated_code.artifactId:
            entries.append(MetricsReportService._entry("Repaired code", "repaired_code", repair_artifact))
        if optimized_artifact is not None:
            entries.append(MetricsReportService._entry("Optimized code", "optimized_code", optimized_artifact))
        return entries

    @staticmethod
    def _entry(label: str, source: str, artifact: CodeArtifact) -> MetricsHistoryEntry:
        return MetricsHistoryEntry(
            label=label,
            source=source,
            artifactId=artifact.artifactId,
            metrics=MetricsService.calculate(artifact.source),
            createdAt=artifact.generatedAt,
        )

    @staticmethod
    def _delta(before: StructuredTextMetrics, after: StructuredTextMetrics) -> MetricsReportDelta:
        return MetricsReportDelta(
            locDelta=after.loc - before.loc,
            cyclomaticComplexityDelta=after.cyclomaticComplexity - before.cyclomaticComplexity,
            maintainabilityIndexDelta=after.maintainabilityIndex - before.maintainabilityIndex,
            estimatedScanTimeDelta=round(after.estimatedScanTimeMs - before.estimatedScanTimeMs, 3),
            locReductionPercent=MetricsService._reduction_percent(before.loc, after.loc),
            complexityReductionPercent=MetricsService._reduction_percent(before.cyclomaticComplexity, after.cyclomaticComplexity),
            maintainabilityImprovementPercent=MetricsService._gain_percent(before.maintainabilityIndex, after.maintainabilityIndex),
            scanTimeReductionPercent=MetricsService._reduction_percent(before.estimatedScanTimeMs, after.estimatedScanTimeMs),
        )

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

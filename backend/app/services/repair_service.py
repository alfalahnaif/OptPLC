from __future__ import annotations

from app.agents import CodeGenerationAgent, DebuggingAgent, ValidationAgent
from app.schemas.contracts import CodeArtifact, DebuggingReport, RepairLoopFinalStatus, RepairLoopReport, ValidationReport
from app.storage.memory import MemoryStore

MAX_ITER = 5


class RepairService:
    def __init__(self, storage: MemoryStore) -> None:
        self.storage = storage

    def run_repair_loop(self, project_id: str, max_iter: int = MAX_ITER) -> RepairLoopReport:
        self.storage.require_project(project_id)
        plan = self.storage.get_plan(project_id)
        if plan is None:
            raise ValueError("PlanObject must be generated before running repair loop.")
        current_artifact = self.storage.get_code_artifact(project_id)
        if current_artifact is None:
            raise ValueError("CodeArtifact must be generated before running repair loop.")

        code_versions: list[CodeArtifact] = self.storage.list_code_artifacts(project_id) or [current_artifact]
        validation_reports: list[ValidationReport] = []
        debugging_reports: list[DebuggingReport] = []
        final_validation: ValidationReport | None = None
        final_status: RepairLoopFinalStatus = "FAILED"

        for attempt in range(1, max_iter + 1):
            validation = ValidationAgent(mode="static").validate(
                project_id=project_id,
                artifact=current_artifact,
                plan=plan,
            )
            self.storage.save_validation_report(project_id, validation)
            validation_reports.append(validation)
            final_validation = validation

            if validation.status == "VERIFIED":
                final_status = "VERIFIED"
                break

            debugging = DebuggingAgent(mode="rule_based").debug(
                project_id=project_id,
                plan=plan,
                artifact=current_artifact,
                validation=validation,
            )
            self.storage.save_debugging_report(project_id, debugging)
            debugging_reports.append(debugging)

            if debugging.status != "PATCH_ADVICE_GENERATED":
                final_status = "FAILED"
                break

            if attempt == max_iter:
                final_status = "ITERATION_LIMIT_REACHED"
                break

            current_artifact = CodeGenerationAgent(mode="template_based").generate_code(
                project_id=project_id,
                plan=plan,
                patch_advice=debugging.patchAdvice,
                suggested_regeneration_prompt=debugging.suggestedRegenerationPrompt,
                iteration=current_artifact.iteration + 1,
            )
            self.storage.save_code_artifact(project_id, current_artifact)
            code_versions.append(current_artifact)

        if final_validation is None:
            raise RuntimeError("Repair loop failed to produce a validation report.")

        report = RepairLoopReport(
            projectId=project_id,
            finalStatus=final_status,
            iterations=len(validation_reports),
            finalCodeArtifact=current_artifact,
            finalValidationReport=final_validation,
            debuggingReports=debugging_reports,
            codeVersions=code_versions,
            validationReports=validation_reports,
            summary=self._summary(final_status, len(validation_reports), len(debugging_reports)),
        )
        self.storage.save_repair_loop_report(project_id, report)
        return report

    @staticmethod
    def _summary(final_status: RepairLoopFinalStatus, iterations: int, debugging_count: int) -> str:
        if final_status == "VERIFIED":
            if debugging_count == 0:
                return "Initial code artifact was already verified; no repair was required."
            return f"Repair loop verified the code after {iterations} validation attempt(s) and {debugging_count} debugging pass(es)."
        if final_status == "ITERATION_LIMIT_REACHED":
            return f"Repair loop stopped after reaching the iteration limit of {iterations} validation attempt(s)."
        return "Repair loop stopped before verification because no actionable repair could be generated."

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import CodeGenerationAgent, DebuggingAgent, ValidationAgent
from app.database.repository import Repository
from app.schemas.contracts import (
    CodeArtifact,
    DebuggingReport,
    PlanObject,
    RepairLoopFinalStatus,
    RepairLoopReport,
    ValidationReport,
)

MAX_ITER = 5


class RepairService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repository = Repository()

    async def run_repair_loop(self, project_id: str, max_iter: int = MAX_ITER) -> RepairLoopReport:
        await self.repository.require_project(self.db, project_id)
        session = await self.repository.get_or_create_project_session(self.db, project_id)

        if session.plan_object is None:
            raise ValueError("PlanObject must be generated before running repair loop.")
        plan = PlanObject.model_validate(session.plan_object)

        if session.code_artifact is None:
            raise ValueError("CodeArtifact must be generated before running repair loop.")
        current_artifact = CodeArtifact.model_validate(session.code_artifact)

        code_versions: list[CodeArtifact] = [CodeArtifact.model_validate(item) for item in (session.code_artifact_history or [])]
        if not code_versions:
            code_versions = [current_artifact]

        validation_reports: list[ValidationReport] = []
        debugging_reports: list[DebuggingReport] = []
        final_validation: ValidationReport | None = None
        final_status: RepairLoopFinalStatus = "FAILED"
        session_state = session.state
        validation_history_payload = list(session.validation_report_history or [])
        debugging_history_payload = list(session.debugging_report_history or [])
        code_history_payload = list(session.code_artifact_history or [])

        for attempt in range(1, max_iter + 1):
            validation = ValidationAgent(mode="static").validate(
                project_id=project_id,
                artifact=current_artifact,
                plan=plan,
            )
            validation_history_payload.append(validation.model_dump())
            session = await self.repository.update_session_state(
                self.db,
                session.id,
                session_state,
                validation_result=validation.model_dump(),
                validation_report=validation.model_dump(),
                validation_report_history=validation_history_payload,
            )
            session_state = session.state
            validation_reports.append(validation)
            final_validation = validation

            if validation.status == "VERIFIED":
                final_status = "VERIFIED"
                break

            debugging = await DebuggingAgent(mode="llm").debug(
                project_id=project_id,
                plan=plan,
                artifact=current_artifact,
                validation=validation,
                iteration=attempt,
            )
            debugging_history_payload.append(debugging.model_dump())
            session = await self.repository.update_session_state(
                self.db,
                session.id,
                session_state,
                debugging_report=debugging.model_dump(),
                debugging_report_history=debugging_history_payload,
            )
            session_state = session.state
            debugging_reports.append(debugging)

            if debugging.status != "PATCH_ADVICE_GENERATED":
                final_status = "FAILED"
                break

            if attempt == max_iter:
                final_status = "ITERATION_LIMIT_REACHED"
                break

            current_artifact = await CodeGenerationAgent(mode="template_based").generate_code(
                project_id=project_id,
                plan=plan,
                patch_advice=debugging.patchAdvice,
                suggested_regeneration_prompt=debugging.suggestedRegenerationPrompt,
                iteration=current_artifact.iteration + 1,
            )
            code_history_payload.append(current_artifact.model_dump())
            session = await self.repository.update_session_state(
                self.db,
                session.id,
                session_state,
                code_artifact=current_artifact.model_dump(),
                code_artifact_history=code_history_payload,
                st_code=current_artifact.source,
            )
            session_state = session.state
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
        await self.repository.update_session_state(
            self.db,
            session.id,
            session_state,
            repair_loop_report=report.model_dump(),
        )
        await self.db.commit()
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

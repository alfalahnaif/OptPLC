from __future__ import annotations

import logging
import re
import json
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import CodeGenerationAgent, DebuggingAgent, OptimizationAgent, PlanningAgent, ValidationAgent
from app.config import settings
from app.database.repository import Repository
from app.schemas.contracts import (
    CodeArtifact,
    CreateProjectRequest,
    DebuggingReport,
    FinalReport,
    MetricsHistoryEntry,
    MetricsReport,
    MetricsReportDelta,
    MetricsSource,
    OptimizationReport,
    PlanObject,
    Project,
    RepairLoopReport,
    RequirementInput,
    RequirementPayload,
    StructuredTextMetrics,
    ValidationReport,
    WorkflowEvent,
)
from app.services.metrics_service import MetricsService

logger = logging.getLogger(__name__)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class ProjectService:
    """Async project service backed by SQLAlchemy repository state."""

    def __init__(self, db: AsyncSession, repository: Repository | None = None) -> None:
        self.db = db
        self.repository = repository or Repository()

    async def create_project(self, request: CreateProjectRequest) -> Project:
        project_id = await self._next_project_id()
        model = await self.repository.create_project(
            self.db,
            {
                "id": project_id,
                "name": request.name,
                "domain": request.domain,
                "description": request.description,
                "standard": "IEC 61131-3",
                "target_language": request.targetLanguage,
                "complexity_tier": request.complexityTier,
                "status": "draft",
            },
        )
        await self.db.commit()
        return self._to_project_contract(model)

    async def list_projects(self) -> list[Project]:
        models = await self.repository.list_projects(self.db)
        return [self._to_project_contract(model) for model in models]

    async def get_project(self, project_id: str) -> Project | None:
        model = await self.repository.get_project(self.db, project_id)
        if model is None:
            return None
        return self._to_project_contract(model)

    async def get_requirements(self, project_id: str) -> RequirementPayload | None:
        project = await self.repository.require_project(self.db, project_id)
        session = await self.repository.get_latest_session_for_project(self.db, project_id)
        if session is None or not session.requirement_input:
            return {
                "projectId": project_id,
                "text": "",
                "safetyConstraints": [],
                "performanceTargets": {
                    "maxScanTimeMs": 5,
                    "maxCyclomaticComplexity": 8,
                    "minMaintainabilityIndex": 75,
                    "maxIterations": 5,
                },
                "confirmedOutputs": [],
                "confirmedInputs": [],
            }

        requirement_input = RequirementInput.model_validate(session.requirement_input)
        submitted_at = session.created_at.isoformat() if session.created_at else None
        return RequirementPayload(
            projectId=requirement_input.projectId,
            text=requirement_input.text,
            safetyConstraints=list(requirement_input.safetyConstraints),
            confirmedOutputs=list(requirement_input.confirmedOutputs),
            confirmedInputs=list(requirement_input.confirmedInputs),
            performanceTargets=requirement_input.performanceTargets,
            domain=requirement_input.domain or project.domain,
            complexityTier=requirement_input.complexityTier or project.complexity_tier,
            submittedAt=submitted_at,
            updatedAt=project.updated_at.isoformat(),
        )

    async def analyze_requirement(
        self,
        project_id: str,
        text: str,
        safety_constraints: list[str],
    ) -> dict[str, Any]:
        """Lightweight LLM analysis for live requirement preview."""
        from app.agents.llm_client import llm_complete

        analysis_system = """You are an IEC 61131-3 PLC I/O analyst.
Extract signals and constraints from the control requirement.
Return ONLY valid JSON - no prose, no markdown.

Schema:
{
  "domain": "Motor Control|Process Control|Traffic Control|Safety Interlock|Sequential Batch",
  "confidence": 0.0-1.0,
  "inferred_inputs": [
    {"name": str, "type": "BOOL|INT|REAL|TIME", "source": "Operator|Safety|Sensor|Timer", "description": str}
  ],
  "suggested_outputs": [
    {"name": str, "type": "BOOL", "description": str, "confirmed": false}
  ],
  "suggested_internals": [
    {"name": str, "type": "BOOL|INT", "description": str}
  ],
  "safety_constraints": [str],
  "suggested_constraints": [str]
}

Rules:
- Extract ALL named signals from the text - do not miss any
- Mark signals explicitly named in the text as inputs
- Mark signals that are controlled outputs (valves, motors, indicators)
- Infer internal state variables needed (step counters, fault flags)
- Copy safety constraints VERBATIM from the safetyConstraints list
- suggested_constraints = additional constraints implied by the text but not stated
- confidence = how certain you are of the domain classification (0.0-1.0)"""

        normalized_constraints = [item.strip() for item in safety_constraints if isinstance(item, str) and item.strip()]
        if normalized_constraints:
            constraints_block = "\n".join(f"- {constraint}" for constraint in normalized_constraints)
        else:
            constraints_block = "None stated yet."
        user_content = (
            f"REQUIREMENT TEXT:\n{text}\n\n"
            f"SAFETY CONSTRAINTS ALREADY STATED:\n{constraints_block}\n\n"
            "Analyze and extract all signals."
        )
        response = await llm_complete(
            system=analysis_system,
            messages=[{"role": "user", "content": user_content}],
            temperature=0.1,
            max_tokens=800,
        )

        cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", response.content).strip()
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            raise ValueError("LLM analysis response must be a JSON object.")
        parsed["projectId"] = project_id
        parsed["analyzedAt"] = datetime.utcnow().isoformat() + "Z"
        parsed["source"] = "llm"
        return parsed

    async def submit_requirements(self, project_id: str, request: RequirementInput) -> WorkflowEvent:
        project = await self.repository.require_project(self.db, project_id)
        if request.projectId != project_id:
            raise ValueError("Requirement projectId must match the route project id.")

        session = await self.repository.get_or_create_project_session(self.db, project_id)
        event = WorkflowEvent(
            id=f"{project_id}-wf-requirements-{self._next_iteration(session.workflow_events)}",
            projectId=project_id,
            agent="Project Service",
            status="completed",
            iteration=1,
            inputSummary="Natural-language PLC requirement stored",
            outputSummary="Requirement input persisted for planning.",
            durationMs=0,
            createdAt=utc_now(),
        )

        workflow_events = self._append_history(session.workflow_events, event)
        await self.repository.update_session_state(
            self.db,
            session.id,
            "requirements_submitted",
            requirement=request.text,
            requirement_input=request.model_dump(),
            safety_constraints=list(request.safetyConstraints),
            workflow_events=workflow_events,
        )
        await self.repository.update_project(self.db, project.id, status="planned")
        await self.db.commit()
        return event

    async def create_plan(self, project_id: str) -> PlanObject:
        project = await self.repository.require_project(self.db, project_id)
        session = await self.repository.get_or_create_project_session(self.db, project_id)

        requirement_input = self._require_contract(
            session.requirement_input,
            RequirementInput,
            "Requirements must be submitted before planning.",
        )
        planning_requirement_text = requirement_input.text
        if requirement_input.confirmedInputs:
            planning_requirement_text += (
                "\n\nCONFIRMED INPUT SIGNALS (ENGINEER-VERIFIED):\n"
                + "\n".join(f"- {item}" for item in requirement_input.confirmedInputs)
            )
        plan = await PlanningAgent(mode="llm").generate_plan(
            project_id=project_id,
            requirement_text=planning_requirement_text,
            safety_constraints=requirement_input.safetyConstraints,
            performance_targets=requirement_input.performanceTargets,
            confirmed_outputs=requirement_input.confirmedOutputs,
            domain=requirement_input.domain or project.domain,
            complexity_tier=requirement_input.complexityTier or project.complexity_tier,
        )
        event = WorkflowEvent(
            id=f"{project_id}-wf-plan-{self._next_iteration(session.workflow_events)}",
            projectId=project_id,
            agent="Planning Agent",
            status="completed",
            iteration=1,
            inputSummary="Requirement and constraints",
            outputSummary="Plan Object generated",
            durationMs=0,
            createdAt=utc_now(),
        )
        await self.repository.update_session_state(
            self.db,
            session.id,
            "planned",
            plan_object=plan.model_dump(),
            workflow_events=self._append_history(session.workflow_events, event),
        )
        await self.repository.update_project(self.db, project_id, status="planned")
        await self.db.commit()
        return plan

    async def get_plan(self, project_id: str) -> PlanObject | None:
        await self.repository.require_project(self.db, project_id)
        session = await self.repository.get_latest_session_for_project(self.db, project_id)
        if session is None or session.plan_object is None:
            return None
        return PlanObject.model_validate(session.plan_object)

    async def generate_code(self, project_id: str) -> CodeArtifact:
        await self.repository.require_project(self.db, project_id)
        session = await self.repository.get_or_create_project_session(self.db, project_id)
        plan = self._require_contract(
            session.plan_object,
            PlanObject,
            "PlanObject must be generated before code generation.",
        )
        iteration = self._next_code_iteration(session.code_artifact_history)
        artifact = await CodeGenerationAgent(mode="llm").generate_code(
            project_id=project_id,
            plan=plan,
            iteration=iteration,
        )
        code_history = self._append_history(session.code_artifact_history, artifact)
        event = WorkflowEvent(
            id=f"{project_id}-wf-generate-{self._next_iteration(session.workflow_events)}",
            projectId=project_id,
            agent="Code Generation Agent",
            status="completed",
            iteration=iteration,
            inputSummary="Plan Object",
            outputSummary="Structured Text artifact generated",
            durationMs=0,
            createdAt=utc_now(),
        )
        await self.repository.update_session_state(
            self.db,
            session.id,
            "generated",
            code_artifact=artifact.model_dump(),
            code_artifact_history=code_history,
            st_code=artifact.source,
            workflow_events=self._append_history(session.workflow_events, event),
        )
        await self.repository.update_project(self.db, project_id, status="generated")
        await self.db.commit()
        return artifact

    async def get_code(self, project_id: str) -> CodeArtifact | None:
        await self.repository.require_project(self.db, project_id)
        session = await self.repository.get_latest_session_for_project(self.db, project_id)
        if session is None or session.code_artifact is None:
            return None
        return CodeArtifact.model_validate(session.code_artifact)

    async def validate_code(self, project_id: str) -> ValidationReport:
        await self.repository.require_project(self.db, project_id)
        session = await self.repository.get_or_create_project_session(self.db, project_id)
        plan = self._require_contract(
            session.plan_object,
            PlanObject,
            "PlanObject must be generated before validation.",
        )
        artifact = self._require_contract(
            session.code_artifact,
            CodeArtifact,
            "CodeArtifact must be generated before validation.",
        )
        report = ValidationAgent(mode="static").validate(
            project_id=project_id,
            artifact=artifact,
            plan=plan,
        )
        history = self._append_history(session.validation_report_history, report)
        await self.repository.update_session_state(
            self.db,
            session.id,
            "validated" if report.status == "VERIFIED" else "failed",
            validation_result=report.model_dump(),
            validation_report=report.model_dump(),
            validation_report_history=history,
        )
        await self.repository.update_project(
            self.db,
            project_id,
            status="validated" if report.status == "VERIFIED" else "failed",
        )
        await self.db.commit()
        return report

    async def get_validation(self, project_id: str) -> ValidationReport | None:
        await self.repository.require_project(self.db, project_id)
        session = await self.repository.get_latest_session_for_project(self.db, project_id)
        if session is None:
            return None
        payload = session.validation_report or session.validation_result
        if payload is None:
            return None
        return ValidationReport.model_validate(payload)

    async def debug_code(self, project_id: str) -> DebuggingReport:
        await self.repository.require_project(self.db, project_id)
        session = await self.repository.get_or_create_project_session(self.db, project_id)
        plan = self._require_contract(
            session.plan_object,
            PlanObject,
            "PlanObject must be generated before debugging.",
        )
        artifact = self._require_contract(
            session.code_artifact,
            CodeArtifact,
            "CodeArtifact must be generated before debugging.",
        )
        validation = self._require_contract(
            session.validation_report or session.validation_result,
            ValidationReport,
            "ValidationReport must be generated before debugging.",
        )
        report = await DebuggingAgent(mode="llm").debug(
            project_id=project_id,
            plan=plan,
            artifact=artifact,
            validation=validation,
            iteration=1,
        )
        history = self._append_history(session.debugging_report_history, report)
        await self.repository.update_session_state(
            self.db,
            session.id,
            "debugged",
            debugging_report=report.model_dump(),
            debugging_report_history=history,
        )
        await self.db.commit()
        return report

    async def get_debugging(self, project_id: str) -> DebuggingReport | None:
        await self.repository.require_project(self.db, project_id)
        session = await self.repository.get_latest_session_for_project(self.db, project_id)
        if session is None or session.debugging_report is None:
            return None
        return DebuggingReport.model_validate(session.debugging_report)

    async def run_repair_loop(self, project_id: str, max_iter: int | None = None) -> RepairLoopReport:
        MAX_WALL_SECONDS = 90
        loop_start = time.monotonic()
        if max_iter is None:
            max_iter = settings.max_iter
        if max_iter < 1:
            raise ValueError("max_iter must be at least 1.")

        await self.repository.require_project(self.db, project_id)
        session = await self.repository.get_or_create_project_session(self.db, project_id)
        plan = self._require_contract(
            session.plan_object,
            PlanObject,
            "PlanObject must be generated before running repair loop.",
        )
        current_artifact = self._require_contract(
            session.code_artifact,
            CodeArtifact,
            "CodeArtifact must be generated before running repair loop.",
        )
        code_versions = [CodeArtifact.model_validate(item) for item in (session.code_artifact_history or [])]
        if not code_versions:
            code_versions = [current_artifact]
        validation_reports: list[ValidationReport] = []
        debugging_reports: list[DebuggingReport] = []
        final_status = "FAILED"
        timed_out = False

        for attempt in range(1, max_iter + 1):
            elapsed = time.monotonic() - loop_start
            if elapsed > MAX_WALL_SECONDS:
                timed_out = True
                logger.warning(
                    "[RepairLoop] Time budget exceeded (%ss > %ss) after %s iterations. Returning best result.",
                    f"{elapsed:.0f}",
                    MAX_WALL_SECONDS,
                    attempt - 1,
                )
                break
            logger.info("[RepairLoop] iteration %s/%s (elapsed %ss)", attempt, max_iter, f"{elapsed:.0f}")

            validation = ValidationAgent(mode="static").validate(
                project_id=project_id,
                artifact=current_artifact,
                plan=plan,
            )
            validation_reports.append(validation)
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
            debugging_reports.append(debugging)
            if debugging.status != "PATCH_ADVICE_GENERATED":
                final_status = "FAILED"
                break
            if attempt == max_iter:
                final_status = "ITERATION_LIMIT_REACHED"
                break

            current_artifact = await CodeGenerationAgent(mode="llm").generate_code(
                project_id=project_id,
                plan=plan,
                patch_advice=debugging.patchAdvice,
                suggested_regeneration_prompt=debugging.suggestedRegenerationPrompt,
                iteration=current_artifact.iteration + 1,
                max_tokens_hint=1500,
            )
            code_versions.append(current_artifact)

        if not validation_reports:
            validation_reports.append(
                self._placeholder_validation_report(project_id=project_id, artifact=current_artifact).model_copy(
                    update={
                        "summary": "Repair loop exited before validation because the server time budget was exceeded.",
                    }
                )
            )
        if timed_out and final_status != "VERIFIED":
            final_status = "ITERATION_LIMIT_REACHED"
            validation_reports[-1] = validation_reports[-1].model_copy(
                update={
                    "status": "TIMEOUT",
                    "summary": (
                        "Repair loop time budget exceeded before verification; returning the latest generated artifact."
                    ),
                }
            )

        final_validation = validation_reports[-1]
        summary = (
            "Repair loop stopped because the server time budget was exceeded; returning the latest generated artifact."
            if timed_out and final_status != "VERIFIED"
            else self._repair_summary(final_status, len(validation_reports), len(debugging_reports))
        )
        report = RepairLoopReport(
            projectId=project_id,
            finalStatus=final_status,  # type: ignore[arg-type]
            iterations=len(validation_reports),
            finalCodeArtifact=current_artifact,
            finalValidationReport=final_validation,
            debuggingReports=debugging_reports,
            codeVersions=code_versions,
            validationReports=validation_reports,
            summary=summary,
        )

        validation_history = self._append_many_history(session.validation_report_history, validation_reports)
        debugging_history = self._append_many_history(session.debugging_report_history, debugging_reports)
        code_history = self._append_many_history(session.code_artifact_history, code_versions[1:]) if len(code_versions) > 1 else (session.code_artifact_history or [code_versions[0].model_dump()])
        await self.repository.update_session_state(
            self.db,
            session.id,
            "validated" if final_status == "VERIFIED" else "failed",
            code_artifact=current_artifact.model_dump(),
            code_artifact_history=code_history,
            st_code=current_artifact.source,
            validation_result=final_validation.model_dump(),
            validation_report=final_validation.model_dump(),
            validation_report_history=validation_history,
            debugging_report=(debugging_reports[-1].model_dump() if debugging_reports else session.debugging_report),
            debugging_report_history=debugging_history,
            repair_loop_report=report.model_dump(),
        )
        await self.repository.update_project(
            self.db,
            project_id,
            status="validated" if final_status == "VERIFIED" else "failed",
        )
        await self.db.commit()
        return report

    async def get_optimization(self, project_id: str) -> OptimizationReport | None:
        await self.repository.require_project(self.db, project_id)
        session = await self.repository.get_latest_session_for_project(self.db, project_id)
        if session is None or session.optimization_report is None:
            return None
        return OptimizationReport.model_validate(session.optimization_report)

    async def optimize_code(self, project_id: str) -> OptimizationReport:
        await self.repository.require_project(self.db, project_id)
        session = await self.repository.get_or_create_project_session(self.db, project_id)
        plan = self._require_contract(
            session.plan_object,
            PlanObject,
            "PlanObject must be generated before optimization.",
        )
        artifact = self._require_contract(
            session.code_artifact,
            CodeArtifact,
            "CodeArtifact must be generated before optimization.",
        )
        validation = self._require_contract(
            session.validation_report or session.validation_result,
            ValidationReport,
            "ValidationReport must be generated before optimization.",
        )
        if validation.status != "VERIFIED":
            raise ValueError("Code must be verified before optimization. Run validation or repair loop first.")
        repair_loop_report = RepairLoopReport.model_validate(session.repair_loop_report) if session.repair_loop_report else None
        report = await OptimizationAgent(mode="llm").optimize(
            project_id=project_id,
            artifact=artifact,
            plan=plan,
            validation=validation,
            repair_loop_report=repair_loop_report,
        )
        history = self._append_history(session.optimization_report_history, report)
        code_history = self._append_history(session.code_artifact_history, report.optimizedCode)
        post_optimization_validation = ValidationAgent(mode="static").validate(
            project_id=project_id,
            artifact=report.optimizedCode,
            plan=plan,
        )
        await self.repository.update_session_state(
            self.db,
            session.id,
            "optimized",
            optimization_report=report.model_dump(),
            optimization_report_history=history,
            code_artifact=report.optimizedCode.model_dump(),
            code_artifact_history=code_history,
            st_code_pre_opt=artifact.source,
            st_code=report.optimizedCode.source,
            validation_result=post_optimization_validation.model_dump(),
            validation_report=post_optimization_validation.model_dump(),
        )
        await self.repository.update_project(self.db, project_id, status="optimized")
        await self.db.commit()
        return report

    async def get_metrics(self, project_id: str) -> MetricsReport:
        await self.repository.require_project(self.db, project_id)
        session = await self.repository.get_or_create_project_session(self.db, project_id)

        plan = self._require_contract(
            session.plan_object,
            PlanObject,
            "PlanObject must be generated before metrics can be computed.",
        )
        _ = plan
        code_history = [CodeArtifact.model_validate(item) for item in (session.code_artifact_history or [])]
        if not code_history and session.code_artifact:
            code_history = [CodeArtifact.model_validate(session.code_artifact)]
        if not code_history:
            raise ValueError("CodeArtifact must be generated before metrics can be computed.")

        generated_code = code_history[0]
        validation_payload = session.validation_report or session.validation_result
        latest_validation = ValidationReport.model_validate(validation_payload) if validation_payload else None
        optimization_report = OptimizationReport.model_validate(session.optimization_report) if session.optimization_report else None
        repair_loop_report = RepairLoopReport.model_validate(session.repair_loop_report) if session.repair_loop_report else None

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
            )
            before_artifact = generated_code
            after_artifact = repair_loop_report.finalCodeArtifact
            summary = "Metrics compare the original generated code with the repaired and revalidated Structured Text artifact."
        else:
            source = MetricsSource(selected="generated_code", generatedCode=generated_code.artifactId)
            before_artifact = generated_code
            after_artifact = generated_code
            summary = "Metrics are based on the generated Structured Text artifact; no repair or optimization report exists yet."

        before_metrics = MetricsService.calculate(before_artifact.source)
        after_metrics = MetricsService.calculate(after_artifact.source)
        history = self._metrics_history(
            generated_code=generated_code,
            repaired_code=(repair_loop_report.finalCodeArtifact if repair_loop_report else None),
            optimized_code=(optimization_report.optimizedCode if optimization_report else None),
        )
        report = MetricsReport(
            projectId=project_id,
            source=source,
            beforeMetrics=before_metrics,
            afterMetrics=after_metrics,
            metricsDelta=self._metrics_delta(before_metrics, after_metrics),
            history=history,
            latestValidationStatus=latest_validation.status if latest_validation else None,
            latestOptimizationStatus=optimization_report.status if optimization_report else None,
            createdAt=utc_now(),
            summary=summary,
        )
        metrics_history = self._append_history(session.metrics_report_history, report)
        await self.repository.update_session_state(
            self.db,
            session.id,
            session.state,
            metrics_report=report.model_dump(),
            metrics_report_history=metrics_history,
            metrics_before=before_metrics.model_dump(),
            metrics_after=after_metrics.model_dump(),
        )
        await self.db.commit()
        return report

    async def get_final_report(self, project_id: str) -> FinalReport:
        project_model = await self.repository.require_project(self.db, project_id)
        session = await self.repository.get_latest_session_for_project(self.db, project_id)
        if session is None:
            raise ValueError("Final report cannot be generated because no project artifacts exist yet.")

        project = self._to_project_contract(project_model)
        requirement = RequirementInput.model_validate(session.requirement_input) if session.requirement_input else None
        plan = PlanObject.model_validate(session.plan_object) if session.plan_object else None
        code = CodeArtifact.model_validate(session.code_artifact) if session.code_artifact else None
        validation_payload = session.validation_report or session.validation_result
        validation = ValidationReport.model_validate(validation_payload) if validation_payload else None
        debugging = DebuggingReport.model_validate(session.debugging_report) if session.debugging_report else None
        repair_loop = RepairLoopReport.model_validate(session.repair_loop_report) if session.repair_loop_report else None
        optimization = OptimizationReport.model_validate(session.optimization_report) if session.optimization_report else None
        metrics = MetricsReport.model_validate(session.metrics_report) if session.metrics_report else None

        meaningful_artifacts = any(
            [
                requirement is not None,
                plan is not None,
                code is not None,
                validation is not None,
                debugging is not None,
                repair_loop is not None,
                optimization is not None,
                metrics is not None,
            ]
        )
        if not meaningful_artifacts:
            raise ValueError("Final report cannot be generated because no project artifacts exist yet.")

        code_for_placeholders = code or self._placeholder_code_artifact(project_id=project_id, source_plan_id=project_id)
        validation_report = validation or self._placeholder_validation_report(project_id=project_id, artifact=code_for_placeholders)
        optimization_report = optimization or self._placeholder_optimization_report(
            project_id=project_id,
            artifact=code_for_placeholders,
            validation=validation_report,
        )
        metrics_report = metrics or self._placeholder_metrics_report(
            project_id=project_id,
            artifact=code_for_placeholders,
            validation=validation_report,
            optimization=optimization_report,
        )

        validation_summary = (
            validation.summary
            if validation is not None
            else "Validation has not been run yet."
        )
        debugging_summary = (
            debugging.rootCauseSummary
            if debugging is not None
            else "Debugging has not been run yet."
        )
        repair_loop_summary = (
            repair_loop.summary
            if repair_loop is not None
            else "Repair loop has not been run yet."
        )
        optimization_summary = (
            optimization.summary
            if optimization is not None
            else "Optimization has not been run yet."
        )
        metrics_summary = (
            metrics.summary
            if metrics is not None
            else "Metrics have not been generated yet."
        )
        final_status_summary = self._final_status_summary(
            project_status=project.status,
            validation=validation,
            optimization=optimization,
            metrics=metrics,
        )
        recommendations = self._recommendations(
            validation=validation,
            debugging=debugging,
            repair_loop=repair_loop,
            optimization=optimization,
            metrics=metrics,
        )
        limitations_disclaimer = (
            "This report is generated from deterministic PLCForge pipeline artifacts. "
            "Formal solver verification, benchmark runner execution, and PDF certificate export remain future work."
        )
        summary = (
            f"{final_status_summary} "
            f"{validation_summary} {optimization_summary} {metrics_summary}"
        ).strip()

        return FinalReport(
            projectId=project_id,
            reportId=f"{project_id}-final-report-{utc_now()}",
            generatedAt=utc_now(),
            summary=summary,
            validation=validation_report,
            optimization=optimization_report,
            metrics=metrics_report,
            project=project,
            requirement=requirement,
            planObject=plan,
            codeArtifact=code,
            debugging=debugging,
            repairLoop=repair_loop,
            validationSummary=validation_summary,
            debuggingSummary=debugging_summary,
            repairLoopSummary=repair_loop_summary,
            optimizationSummary=optimization_summary,
            metricsSummary=metrics_summary,
            finalStatusSummary=final_status_summary,
            recommendations=recommendations,
            limitationsDisclaimer=limitations_disclaimer,
        )

    async def get_final_report_json(self, project_id: str) -> str:
        report = await self.get_final_report(project_id)
        return report.model_dump_json(indent=2)

    async def get_final_report_markdown(self, project_id: str) -> str:
        report = await self.get_final_report(project_id)
        return self._render_final_report_markdown(report)

    async def _next_project_id(self) -> str:
        projects = await self.repository.list_projects(self.db)
        max_suffix = 0
        for project in projects:
            match = re.match(r"PRJ-(\d+)$", project.id)
            if match:
                max_suffix = max(max_suffix, int(match.group(1)))
        return f"PRJ-{max_suffix + 1:04d}"

    @staticmethod
    def _to_project_contract(model: Any) -> Project:
        return Project(
            id=model.id,
            name=model.name,
            domain=model.domain,
            description=model.description,
            standard=model.standard,
            targetLanguage=model.target_language,
            status=model.status,
            createdAt=model.created_at.isoformat(),
            updatedAt=model.updated_at.isoformat(),
        )

    @staticmethod
    def _require_contract(payload: dict[str, Any] | None, contract_type: type[Any], message: str):
        if payload is None:
            raise ValueError(message)
        return contract_type.model_validate(payload)

    @staticmethod
    def _append_history(history: list[dict[str, Any]] | None, value: Any) -> list[dict[str, Any]]:
        existing = list(history or [])
        existing.append(value.model_dump())
        return existing

    @classmethod
    def _append_many_history(cls, history: list[dict[str, Any]] | None, values: list[Any]) -> list[dict[str, Any]]:
        result = list(history or [])
        for value in values:
            result.append(value.model_dump())
        return result

    @staticmethod
    def _next_code_iteration(history: list[dict[str, Any]] | None) -> int:
        if not history:
            return 1
        latest = max((int(item.get("iteration", 0)) for item in history), default=0)
        return latest + 1

    @staticmethod
    def _next_iteration(history: list[dict[str, Any]] | None) -> int:
        return len(history or []) + 1

    @staticmethod
    def _repair_summary(final_status: str, iterations: int, debugging_count: int) -> str:
        if final_status == "VERIFIED":
            if debugging_count == 0:
                return "Initial code artifact was already verified; no repair was required."
            return f"Repair loop verified the code after {iterations} validation attempt(s) and {debugging_count} debugging pass(es)."
        if final_status == "ITERATION_LIMIT_REACHED":
            return f"Repair loop stopped after reaching the iteration limit of {iterations} validation attempt(s)."
        return "Repair loop stopped before verification because no actionable repair could be generated."

    @staticmethod
    def _metrics_history(
        *,
        generated_code: CodeArtifact,
        repaired_code: CodeArtifact | None,
        optimized_code: CodeArtifact | None,
    ) -> list[MetricsHistoryEntry]:
        entries = [
            MetricsHistoryEntry(
                label="Generated code",
                source="generated_code",
                artifactId=generated_code.artifactId,
                metrics=MetricsService.calculate(generated_code.source),
                createdAt=generated_code.generatedAt,
            )
        ]
        if repaired_code is not None and repaired_code.artifactId != generated_code.artifactId:
            entries.append(
                MetricsHistoryEntry(
                    label="Repaired code",
                    source="repaired_code",
                    artifactId=repaired_code.artifactId,
                    metrics=MetricsService.calculate(repaired_code.source),
                    createdAt=repaired_code.generatedAt,
                )
            )
        if optimized_code is not None:
            entries.append(
                MetricsHistoryEntry(
                    label="Optimized code",
                    source="optimized_code",
                    artifactId=optimized_code.artifactId,
                    metrics=MetricsService.calculate(optimized_code.source),
                    createdAt=optimized_code.generatedAt,
                )
            )
        return entries

    @staticmethod
    def _metrics_delta(before: StructuredTextMetrics, after: StructuredTextMetrics) -> MetricsReportDelta:
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
    def _placeholder_code_artifact(*, project_id: str, source_plan_id: str) -> CodeArtifact:
        source = "PROGRAM PLC_PLACEHOLDER\nEND_PROGRAM"
        metrics = MetricsService.calculate(source)
        now = utc_now()
        return CodeArtifact(
            projectId=project_id,
            artifactId=f"{project_id}-code-placeholder",
            language="structured-text",
            filename="placeholder.st",
            source=source,
            iteration=0,
            generatedAt=now,
            metrics={
                "loc": metrics.loc,
                "cyclomaticComplexity": metrics.cyclomaticComplexity,
                "maintainabilityIndex": metrics.maintainabilityIndex,
            },
            metadata={
                "generator": "placeholder.v1",
                "iecStandard": "IEC 61131-3",
                "sourcePlanId": source_plan_id,
                "createdAt": now,
                "iteration": 0,
            },
        )

    @staticmethod
    def _placeholder_validation_report(*, project_id: str, artifact: CodeArtifact) -> ValidationReport:
        now = utc_now()
        return ValidationReport(
            projectId=project_id,
            artifactId=artifact.artifactId,
            iteration=max(artifact.iteration, 0),
            status="TIMEOUT",
            syntaxPassed=False,
            formalPassed=False,
            solver="static.v1",
            validator="static.v1",
            checkedAt=now,
            summary="Validation has not been run yet.",
            syntaxErrors=[],
            formalErrors=[],
            safetyResults=[],
            properties=[],
            errors=[],
            counterexample=None,
            counterexamples=[],
        )

    @staticmethod
    def _placeholder_optimization_report(
        *,
        project_id: str,
        artifact: CodeArtifact,
        validation: ValidationReport,
    ) -> OptimizationReport:
        before_metrics = MetricsService.calculate(artifact.source)
        after_metrics = before_metrics
        now = utc_now()
        return OptimizationReport(
            projectId=project_id,
            sourceArtifactId=artifact.artifactId,
            optimizedArtifactId=artifact.artifactId,
            status="CANNOT_OPTIMIZE",
            optimizer="static.v1",
            originalCode=artifact,
            optimizedCode=artifact,
            passes=[],
            beforeMetrics=before_metrics,
            afterMetrics=after_metrics,
            metricsDelta=MetricsService.delta(before_metrics, after_metrics),
            revalidationStatus=validation.status,
            rollbackEvents=[],
            createdAt=now,
            summary="Optimization has not been run yet.",
            revalidated=False,
        )

    @staticmethod
    def _placeholder_metrics_report(
        *,
        project_id: str,
        artifact: CodeArtifact,
        validation: ValidationReport,
        optimization: OptimizationReport,
    ) -> MetricsReport:
        before_metrics = MetricsService.calculate(artifact.source)
        after_metrics = before_metrics
        now = utc_now()
        return MetricsReport(
            projectId=project_id,
            source=MetricsSource(selected="generated_code", generatedCode=artifact.artifactId),
            beforeMetrics=before_metrics,
            afterMetrics=after_metrics,
            metricsDelta=ProjectService._metrics_delta(before_metrics, after_metrics),
            history=[],
            latestValidationStatus=validation.status,
            latestOptimizationStatus=optimization.status,
            createdAt=now,
            summary="Metrics have not been generated yet.",
        )

    @staticmethod
    def _final_status_summary(
        *,
        project_status: str,
        validation: ValidationReport | None,
        optimization: OptimizationReport | None,
        metrics: MetricsReport | None,
    ) -> str:
        parts = [f"Project status is '{project_status}'."]
        if validation is not None:
            parts.append(f"Validation status: {validation.status}.")
        else:
            parts.append("Validation status: not generated yet.")
        if optimization is not None:
            parts.append(f"Optimization status: {optimization.status}.")
        else:
            parts.append("Optimization status: not generated yet.")
        if metrics is not None:
            parts.append("Metrics report is available.")
        else:
            parts.append("Metrics report is not generated yet.")
        return " ".join(parts)

    @staticmethod
    def _recommendations(
        *,
        validation: ValidationReport | None,
        debugging: DebuggingReport | None,
        repair_loop: RepairLoopReport | None,
        optimization: OptimizationReport | None,
        metrics: MetricsReport | None,
    ) -> list[str]:
        recommendations: list[str] = []
        if validation is None:
            recommendations.append("Run validation to generate syntax and safety evidence.")
        elif validation.status != "VERIFIED":
            recommendations.append("Address validation issues using debugging guidance before deployment.")
        if debugging is None and validation is not None and validation.status != "VERIFIED":
            recommendations.append("Run debugging to generate patch advice for failing validations.")
        if repair_loop is None and validation is not None and validation.status != "VERIFIED":
            recommendations.append("Run repair loop to regenerate code until validation succeeds.")
        if optimization is None:
            recommendations.append("Run optimization to improve maintainability and scan time.")
        if metrics is None:
            recommendations.append("Generate metrics to quantify code quality and performance.")
        if not recommendations:
            recommendations.append("Pipeline artifacts are complete. Proceed with controlled deployment review.")
        return recommendations

    @staticmethod
    def _render_final_report_markdown(report: FinalReport) -> str:
        requirement_text = report.requirement.text if report.requirement else "Not generated yet"
        plan_summary = (
            f"Inputs: {len(report.planObject.inputs)} | Outputs: {len(report.planObject.outputs)} | "
            f"Safety constraints: {len(report.planObject.safetyConstraints)}"
            if report.planObject
            else "Not generated yet"
        )
        code_text = report.codeArtifact.source if report.codeArtifact else "Not generated yet"
        debugging_summary = report.debuggingSummary if report.debugging else "Not generated yet"
        repair_loop_summary = report.repairLoopSummary if report.repairLoop else "Not generated yet"
        optimization_summary = report.optimizationSummary if report.optimization else "Not generated yet"
        metrics_summary = report.metricsSummary if report.metrics else "Not generated yet"
        recommendations = "\n".join(f"- {item}" for item in report.recommendations) if report.recommendations else "- Not generated yet"

        return (
            f"# PLCForge Final Report - {report.projectId}\n\n"
            f"Generated at: {report.generatedAt}\n\n"
            f"## Project Metadata\n\n"
            f"- Project ID: {report.project.id}\n"
            f"- Name: {report.project.name}\n"
            f"- Domain: {report.project.domain}\n"
            f"- Status: {report.project.status}\n"
            f"- Standard: {report.project.standard}\n"
            f"- Target Language: {report.project.targetLanguage}\n\n"
            f"## Requirement\n\n"
            f"{requirement_text}\n\n"
            f"## Plan Summary\n\n"
            f"{plan_summary}\n\n"
            f"## Generated Code\n\n"
            f"```iecst\n{code_text}\n```\n\n"
            f"## Validation Summary\n\n"
            f"{report.validationSummary}\n\n"
            f"## Debugging Summary\n\n"
            f"{debugging_summary}\n\n"
            f"## Repair Loop Summary\n\n"
            f"{repair_loop_summary}\n\n"
            f"## Optimization Summary\n\n"
            f"{optimization_summary}\n\n"
            f"## Metrics Summary\n\n"
            f"{metrics_summary}\n\n"
            f"## Final Status Summary\n\n"
            f"{report.finalStatusSummary}\n\n"
            f"## Recommendations\n\n"
            f"{recommendations}\n\n"
            f"## Limitations Disclaimer\n\n"
            f"{report.limitationsDisclaimer}\n"
        )

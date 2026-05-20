from datetime import datetime, timezone

from app.agents import CodeGenerationAgent, DebuggingAgent, OptimizationAgent, PlanningAgent, ValidationAgent
from app.schemas.contracts import (
    CodeArtifact,
    CreateProjectRequest,
    DebuggingReport,
    OptimizationReport,
    PlanObject,
    Project,
    RequirementInput,
    ValidationReport,
    WorkflowEvent,
)
from app.storage.memory import MemoryStore


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class ProjectService:
    def __init__(self, storage: MemoryStore) -> None:
        self.storage = storage

    def create_project(self, request: CreateProjectRequest) -> Project:
        now = utc_now()
        project = Project(
            id=self.storage.next_project_id(),
            name=request.name,
            domain=request.domain,
            description=request.description,
            standard="IEC 61131-3",
            targetLanguage=request.targetLanguage,
            status="draft",
            createdAt=now,
            updatedAt=now,
        )
        self.storage.save_project(project)
        self.storage.save_project_complexity(project.id, request.complexityTier)
        return project

    def list_projects(self) -> list[Project]:
        return self.storage.list_projects()

    def get_project(self, project_id: str) -> Project | None:
        return self.storage.get_project(project_id)

    def submit_requirements(self, project_id: str, request: RequirementInput) -> WorkflowEvent:
        project = self.storage.require_project(project_id)
        if request.projectId != project_id:
            raise ValueError("Requirement projectId must match the route project id.")

        self.storage.save_requirement(project_id, request)
        updated_project = project.model_copy(update={"status": "planned", "updatedAt": utc_now()})
        self.storage.save_project(updated_project)

        event = WorkflowEvent(
            id=f"{project_id}-wf-planning-1",
            projectId=project_id,
            agent="Planning Agent",
            status="completed",
            iteration=1,
            inputSummary="Natural-language requirement accepted",
            outputSummary="Requirement envelope stored; ready for Plan Object generation",
            durationMs=4200,
            createdAt=utc_now(),
        )
        self.storage.save_workflow_event(project_id, event)
        return event

    def create_plan(self, project_id: str) -> PlanObject:
        project = self.storage.require_project(project_id)
        requirement = self.storage.get_requirement(project_id)
        if requirement is None:
            raise ValueError("Requirements must be submitted before creating a plan.")
        if not requirement.text.strip():
            raise ValueError("Requirement text must not be empty.")

        plan = PlanningAgent(mode="rule_based").generate_plan(
            project_id=project_id,
            requirement_text=requirement.text,
            safety_constraints=requirement.safetyConstraints,
            performance_targets=requirement.performanceTargets,
            domain=project.domain,
            complexity_tier=self.storage.get_project_complexity(project_id),
        )
        self.storage.save_plan(project_id, plan)
        self.storage.save_project(project.model_copy(update={"status": "planned", "updatedAt": utc_now()}))
        return plan

    def generate_code(self, project_id: str) -> CodeArtifact:
        project = self.storage.require_project(project_id)
        plan = self.storage.get_plan(project_id)
        if plan is None:
            raise ValueError("PlanObject must be generated before code generation.")

        artifact = CodeGenerationAgent(mode="template_based").generate_code(
            project_id=project_id,
            plan=plan,
        )
        self.storage.save_code_artifact(project_id, artifact)
        self.storage.save_project(project.model_copy(update={"status": "generated", "updatedAt": utc_now()}))
        return artifact

    def validate_code(self, project_id: str) -> ValidationReport:
        project = self.storage.require_project(project_id)
        plan = self.storage.get_plan(project_id)
        if plan is None:
            raise ValueError("PlanObject must be generated before validation.")
        artifact = self.storage.get_code_artifact(project_id)
        if artifact is None:
            raise ValueError("CodeArtifact must be generated before validation.")

        report = ValidationAgent(mode="static").validate(
            project_id=project_id,
            artifact=artifact,
            plan=plan,
        )
        self.storage.save_validation_report(project_id, report)
        next_status = "validated" if report.status == "VERIFIED" else "failed"
        self.storage.save_project(project.model_copy(update={"status": next_status, "updatedAt": utc_now()}))
        return report

    def debug_code(self, project_id: str) -> DebuggingReport:
        project = self.storage.require_project(project_id)
        plan = self.storage.get_plan(project_id)
        if plan is None:
            raise ValueError("PlanObject must be generated before debugging.")
        artifact = self.storage.get_code_artifact(project_id)
        if artifact is None:
            raise ValueError("CodeArtifact must be generated before debugging.")
        validation = self.storage.get_validation_report(project_id)
        if validation is None:
            raise ValueError("ValidationReport must be generated before debugging.")

        report = DebuggingAgent(mode="rule_based").debug(
            project_id=project_id,
            plan=plan,
            artifact=artifact,
            validation=validation,
        )
        self.storage.save_debugging_report(project_id, report)
        self.storage.save_project(project.model_copy(update={"status": project.status, "updatedAt": utc_now()}))
        return report

    def optimize_code(self, project_id: str) -> OptimizationReport:
        project = self.storage.require_project(project_id)
        artifact = self.storage.get_code_artifact(project_id)
        if artifact is None:
            raise ValueError("CodeArtifact must be generated before optimization.")
        plan = self.storage.get_plan(project_id)
        if plan is None:
            raise ValueError("PlanObject must be generated before optimization.")
        validation = self.storage.get_validation_report(project_id)
        if validation is None:
            raise ValueError("ValidationReport must be generated before optimization.")
        if validation.status != "VERIFIED":
            raise ValueError("Code must be verified before optimization. Run validation or repair loop first.")

        report = OptimizationAgent(mode="static").optimize(
            project_id=project_id,
            artifact=artifact,
            plan=plan,
            validation=validation,
            repair_loop_report=self.storage.get_repair_loop_report(project_id),
        )
        self.storage.save_optimization_report(project_id, report)
        if report.status in {"OPTIMIZED", "NO_CHANGES"} and report.revalidationStatus == "VERIFIED":
            self.storage.save_code_artifact(project_id, report.optimizedCode)
            final_validation = ValidationAgent(mode="static").validate(
                project_id=project_id,
                artifact=report.optimizedCode,
                plan=plan,
            )
            self.storage.save_validation_report(project_id, final_validation)
            self.storage.save_project(project.model_copy(update={"status": "optimized", "updatedAt": utc_now()}))
        else:
            self.storage.save_project(project.model_copy(update={"status": project.status, "updatedAt": utc_now()}))
        return report

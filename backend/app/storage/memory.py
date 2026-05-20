from threading import Lock

from app.schemas.contracts import CodeArtifact, DebuggingReport, MetricsReport, OptimizationReport, PlanObject, Project, RepairLoopReport, RequirementInput, ValidationReport, WorkflowEvent


class MemoryStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self._projects: dict[str, Project] = {
                "PRJ-0421": Project(
                    id="PRJ-0421",
                    name="Motor Control - Conveyor M-12",
                    domain="Motor Control",
                    description=(
                        "Three-phase motor on conveyor M-12 with start/stop, "
                        "E-stop, overload protection, and explicit reset."
                    ),
                    standard="IEC 61131-3",
                    targetLanguage="Structured Text",
                    status="planned",
                    createdAt="2026-05-17T09:40:00Z",
                    updatedAt="2026-05-17T09:42:18Z",
                )
            }
            self._complexity_tiers: dict[str, str] = {
                "PRJ-0421": "medium",
            }
            self._requirements: dict[str, RequirementInput] = {
                "PRJ-0421": RequirementInput(
                    projectId="PRJ-0421",
                    text=(
                        "Control a three-phase motor on conveyor M-12. The operator starts "
                        "the motor via Start_PB when Stop_PB is not pressed. E_Stop and "
                        "Overload must immediately de-energize the motor. After a fault, "
                        "Reset_PB must acknowledge before restart."
                    ),
                    safetyConstraints=[
                        "Motor must not restart automatically after E-Stop or overload",
                        "E-Stop input must be normally closed; loss of signal triggers fault",
                        "Reset must require explicit operator action",
                        "Fault lamp must reflect latched fault, not transient signal",
                    ],
                    performanceTargets={
                        "maxScanTimeMs": 5,
                        "maxCyclomaticComplexity": 8,
                        "minMaintainabilityIndex": 75,
                        "maxIterations": 5,
                    },
                )
            }
            self._plans: dict[str, PlanObject] = {}
            self._code_artifacts: dict[str, CodeArtifact] = {}
            self._code_artifact_history: dict[str, list[CodeArtifact]] = {}
            self._validation_reports: dict[str, ValidationReport] = {}
            self._validation_report_history: dict[str, list[ValidationReport]] = {}
            self._debugging_reports: dict[str, DebuggingReport] = {}
            self._debugging_report_history: dict[str, list[DebuggingReport]] = {}
            self._optimization_reports: dict[str, OptimizationReport] = {}
            self._optimization_report_history: dict[str, list[OptimizationReport]] = {}
            self._metrics_reports: dict[str, MetricsReport] = {}
            self._metrics_report_history: dict[str, list[MetricsReport]] = {}
            self._repair_loop_reports: dict[str, RepairLoopReport] = {}
            self._workflow_events: dict[str, list[WorkflowEvent]] = {}
            self._sequence = 422

    def next_project_id(self) -> str:
        with self._lock:
            project_id = f"PRJ-{self._sequence:04d}"
            self._sequence += 1
            return project_id

    def save_project(self, project: Project) -> None:
        with self._lock:
            self._projects[project.id] = project

    def save_project_complexity(self, project_id: str, complexity_tier: str) -> None:
        with self._lock:
            self._complexity_tiers[project_id] = complexity_tier

    def get_project_complexity(self, project_id: str) -> str:
        with self._lock:
            return self._complexity_tiers.get(project_id, "medium")

    def list_projects(self) -> list[Project]:
        with self._lock:
            return list(self._projects.values())

    def get_project(self, project_id: str) -> Project | None:
        with self._lock:
            return self._projects.get(project_id)

    def require_project(self, project_id: str) -> Project:
        project = self.get_project(project_id)
        if project is None:
            raise KeyError(project_id)
        return project

    def save_requirement(self, project_id: str, requirement: RequirementInput) -> None:
        with self._lock:
            self._requirements[project_id] = requirement

    def get_requirement(self, project_id: str) -> RequirementInput | None:
        with self._lock:
            return self._requirements.get(project_id)

    def save_plan(self, project_id: str, plan: PlanObject) -> None:
        with self._lock:
            self._plans[project_id] = plan

    def get_plan(self, project_id: str) -> PlanObject | None:
        with self._lock:
            return self._plans.get(project_id)

    def save_code_artifact(self, project_id: str, artifact: CodeArtifact) -> None:
        with self._lock:
            self._code_artifacts[project_id] = artifact
            self._code_artifact_history.setdefault(project_id, []).append(artifact)

    def get_code_artifact(self, project_id: str) -> CodeArtifact | None:
        with self._lock:
            return self._code_artifacts.get(project_id)

    def list_code_artifacts(self, project_id: str) -> list[CodeArtifact]:
        with self._lock:
            history = self._code_artifact_history.get(project_id)
            if history:
                return list(history)
            latest = self._code_artifacts.get(project_id)
            return [latest] if latest else []

    def save_validation_report(self, project_id: str, report: ValidationReport) -> None:
        with self._lock:
            self._validation_reports[project_id] = report
            self._validation_report_history.setdefault(project_id, []).append(report)

    def get_validation_report(self, project_id: str) -> ValidationReport | None:
        with self._lock:
            return self._validation_reports.get(project_id)

    def list_validation_reports(self, project_id: str) -> list[ValidationReport]:
        with self._lock:
            history = self._validation_report_history.get(project_id)
            if history:
                return list(history)
            latest = self._validation_reports.get(project_id)
            return [latest] if latest else []

    def save_debugging_report(self, project_id: str, report: DebuggingReport) -> None:
        with self._lock:
            self._debugging_reports[project_id] = report
            self._debugging_report_history.setdefault(project_id, []).append(report)

    def get_debugging_report(self, project_id: str) -> DebuggingReport | None:
        with self._lock:
            return self._debugging_reports.get(project_id)

    def list_debugging_reports(self, project_id: str) -> list[DebuggingReport]:
        with self._lock:
            history = self._debugging_report_history.get(project_id)
            if history:
                return list(history)
            latest = self._debugging_reports.get(project_id)
            return [latest] if latest else []

    def save_optimization_report(self, project_id: str, report: OptimizationReport) -> None:
        with self._lock:
            self._optimization_reports[project_id] = report
            self._optimization_report_history.setdefault(project_id, []).append(report)

    def get_optimization_report(self, project_id: str) -> OptimizationReport | None:
        with self._lock:
            return self._optimization_reports.get(project_id)

    def list_optimization_reports(self, project_id: str) -> list[OptimizationReport]:
        with self._lock:
            history = self._optimization_report_history.get(project_id)
            if history:
                return list(history)
            latest = self._optimization_reports.get(project_id)
            return [latest] if latest else []

    def save_metrics_report(self, project_id: str, report: MetricsReport) -> None:
        with self._lock:
            self._metrics_reports[project_id] = report
            self._metrics_report_history.setdefault(project_id, []).append(report)

    def get_metrics_report(self, project_id: str) -> MetricsReport | None:
        with self._lock:
            return self._metrics_reports.get(project_id)

    def list_metrics_reports(self, project_id: str) -> list[MetricsReport]:
        with self._lock:
            history = self._metrics_report_history.get(project_id)
            if history:
                return list(history)
            latest = self._metrics_reports.get(project_id)
            return [latest] if latest else []

    def save_repair_loop_report(self, project_id: str, report: RepairLoopReport) -> None:
        with self._lock:
            self._repair_loop_reports[project_id] = report

    def get_repair_loop_report(self, project_id: str) -> RepairLoopReport | None:
        with self._lock:
            return self._repair_loop_reports.get(project_id)

    def save_workflow_event(self, project_id: str, event: WorkflowEvent) -> None:
        with self._lock:
            self._workflow_events.setdefault(project_id, []).append(event)

    def list_workflow_events(self, project_id: str) -> list[WorkflowEvent]:
        with self._lock:
            return list(self._workflow_events.get(project_id, []))


store = MemoryStore()

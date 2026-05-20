from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.contracts import (
    CodeArtifact,
    CreateProjectRequest,
    DebuggingReport,
    MetricsReport,
    OptimizationReport,
    PlanObject,
    Project,
    RepairLoopReport,
    RequirementInput,
    ValidationReport,
    WorkflowEvent,
)
from app.services.repair_service import RepairService
from app.services.metrics_report_service import MetricsReportService
from app.services.project_service import ProjectService
from app.storage.memory import store

router = APIRouter(prefix="/projects", tags=["projects"])


def get_project_service() -> ProjectService:
    return ProjectService(store)


def get_repair_service() -> RepairService:
    return RepairService(store)


def get_metrics_service() -> MetricsReportService:
    return MetricsReportService(store)


@router.post("", response_model=Project, status_code=status.HTTP_201_CREATED)
def create_project(
    request: CreateProjectRequest,
    service: ProjectService = Depends(get_project_service),
) -> Project:
    return service.create_project(request)


@router.get("", response_model=list[Project])
def list_projects(service: ProjectService = Depends(get_project_service)) -> list[Project]:
    return service.list_projects()


@router.get("/{project_id}", response_model=Project)
def get_project(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> Project:
    project = service.get_project(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} was not found.",
        )
    return project


@router.get("/{project_id}/metrics", response_model=MetricsReport)
def get_metrics(
    project_id: str,
    service: MetricsReportService = Depends(get_metrics_service),
) -> MetricsReport:
    try:
        return service.get_metrics(project_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} was not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/{project_id}/requirements", response_model=WorkflowEvent)
def submit_requirements(
    project_id: str,
    request: RequirementInput,
    service: ProjectService = Depends(get_project_service),
) -> WorkflowEvent:
    try:
        return service.submit_requirements(project_id, request)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} was not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/{project_id}/generate", response_model=CodeArtifact)
def generate_code(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> CodeArtifact:
    try:
        return service.generate_code(project_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} was not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/{project_id}/validate", response_model=ValidationReport)
def validate_code(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> ValidationReport:
    try:
        return service.validate_code(project_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} was not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/{project_id}/debug", response_model=DebuggingReport)
def debug_code(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> DebuggingReport:
    try:
        return service.debug_code(project_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} was not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/{project_id}/optimize", response_model=OptimizationReport)
def optimize_code(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> OptimizationReport:
    try:
        return service.optimize_code(project_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} was not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/{project_id}/repair-loop", response_model=RepairLoopReport)
def run_repair_loop(
    project_id: str,
    service: RepairService = Depends(get_repair_service),
) -> RepairLoopReport:
    try:
        return service.run_repair_loop(project_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} was not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/{project_id}/plan", response_model=PlanObject)
def create_plan(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> PlanObject:
    try:
        return service.create_plan(project_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} was not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

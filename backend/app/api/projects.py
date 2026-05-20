from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.schemas.contracts import (
    CodeArtifact,
    CreateProjectRequest,
    DebuggingReport,
    FinalReport,
    MetricsReport,
    OptimizationReport,
    PlanObject,
    Project,
    RepairLoopReport,
    RequirementInput,
    ValidationReport,
    WorkflowEvent,
)
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


def get_project_service(db: AsyncSession = Depends(get_db)) -> ProjectService:
    return ProjectService(db)


@router.post("", response_model=Project, status_code=status.HTTP_201_CREATED)
async def create_project(
    request: CreateProjectRequest,
    service: ProjectService = Depends(get_project_service),
) -> Project:
    return await service.create_project(request)


@router.get("", response_model=list[Project])
async def list_projects(service: ProjectService = Depends(get_project_service)) -> list[Project]:
    return await service.list_projects()


@router.get("/{project_id}", response_model=Project)
async def get_project(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> Project:
    project = await service.get_project(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} was not found.",
        )
    return project


@router.get("/{project_id}/metrics", response_model=MetricsReport)
async def get_metrics(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> MetricsReport:
    try:
        return await service.get_metrics(project_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} was not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/{project_id}/report", response_model=FinalReport)
async def get_final_report(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> FinalReport:
    try:
        return await service.get_final_report(project_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} was not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/{project_id}/report/export/json")
async def export_final_report_json(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> Response:
    try:
        payload = await service.get_final_report_json(project_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} was not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="plcforge_report_{project_id}.json"'},
    )


@router.get("/{project_id}/report/export/markdown")
async def export_final_report_markdown(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> Response:
    try:
        payload = await service.get_final_report_markdown(project_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} was not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return Response(
        content=payload,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="plcforge_report_{project_id}.md"'},
    )


@router.post("/{project_id}/requirements", response_model=WorkflowEvent)
async def submit_requirements(
    project_id: str,
    request: RequirementInput,
    service: ProjectService = Depends(get_project_service),
) -> WorkflowEvent:
    try:
        return await service.submit_requirements(project_id, request)
    except LookupError as exc:
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
async def generate_code(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> CodeArtifact:
    try:
        return await service.generate_code(project_id)
    except LookupError as exc:
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
async def validate_code(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> ValidationReport:
    try:
        return await service.validate_code(project_id)
    except LookupError as exc:
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
async def debug_code(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> DebuggingReport:
    try:
        return await service.debug_code(project_id)
    except LookupError as exc:
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
async def optimize_code(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> OptimizationReport:
    try:
        return await service.optimize_code(project_id)
    except LookupError as exc:
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
async def run_repair_loop(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> RepairLoopReport:
    try:
        return await service.run_repair_loop(project_id)
    except LookupError as exc:
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
async def create_plan(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> PlanObject:
    try:
        return await service.create_plan(project_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} was not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

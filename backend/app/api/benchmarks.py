from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.schemas.contracts import (
    BenchmarkCaseCatalogItem,
    BenchmarkCaseResult,
    BenchmarkCompareRequest,
    BenchmarkComparisonResult,
    BenchmarkRunRequest,
    BenchmarkSummaryResponse,
)
from app.services.benchmark_runner import BenchmarkRunner

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])


def get_benchmark_runner(db: AsyncSession = Depends(get_db)) -> BenchmarkRunner:
    return BenchmarkRunner(db)


@router.get("/cases", response_model=list[BenchmarkCaseCatalogItem])
async def list_benchmark_cases(
    runner: BenchmarkRunner = Depends(get_benchmark_runner),
) -> list[BenchmarkCaseCatalogItem]:
    cases = runner.list_cases()
    return [
        BenchmarkCaseCatalogItem(
            id=entry.id,
            name=entry.name,
            domain=entry.domain,
            complexity=entry.complexity,
        )
        for entry in cases
    ]


@router.post("/run", response_model=BenchmarkCaseResult)
async def run_benchmark_case(
    request: BenchmarkRunRequest,
    runner: BenchmarkRunner = Depends(get_benchmark_runner),
) -> BenchmarkCaseResult:
    try:
        return await runner.execute_case(case_id=request.caseId, mode=request.mode)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/compare", response_model=BenchmarkComparisonResult)
async def compare_benchmark_modes(
    request: BenchmarkCompareRequest,
    runner: BenchmarkRunner = Depends(get_benchmark_runner),
) -> BenchmarkComparisonResult:
    try:
        payload = await runner.run_comparison(case_id=request.caseId)
        return BenchmarkComparisonResult.model_validate(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/run-suite")
async def run_full_suite(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    body = (
        await request.json()
        if request.headers.get("content-type", "").startswith("application/json")
        else {}
    )
    mode = body.get("mode", "all")

    runner = BenchmarkRunner()
    cases = runner.get_available_cases()
    modes_to_run = ["rule_based", "llm", "llm_rag"] if mode == "all" else [mode]

    results: list[dict] = []
    for case_id in cases:
        case_results: dict = {}
        for current_mode in modes_to_run:
            try:
                result = await runner.execute_case(
                    case_id=case_id,
                    mode=current_mode,  # type: ignore[arg-type]
                    db=db,
                )
                case_results[current_mode] = result.model_dump()
            except Exception as exc:
                case_results[current_mode] = {
                    "caseId": case_id,
                    "mode": current_mode,
                    "error": str(exc),
                    "verified": False,
                }
        results.append(
            {
                "caseId": case_id,
                "results": case_results,
            }
        )

    return {
        "status": "completed",
        "totalCases": len(cases),
        "modesRun": modes_to_run,
        "results": results,
    }


@router.get("/results")
async def get_benchmark_results(
    runner: BenchmarkRunner = Depends(get_benchmark_runner),
) -> dict:
    return runner.list_persisted_results()


@router.get("/summary", response_model=BenchmarkSummaryResponse)
async def get_benchmark_summary(
    runner: BenchmarkRunner = Depends(get_benchmark_runner),
) -> BenchmarkSummaryResponse:
    return BenchmarkSummaryResponse.model_validate(runner.summary())

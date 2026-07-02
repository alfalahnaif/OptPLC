from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import CodeGenerationAgent, DebuggingAgent, OptimizationAgent, PlanningAgent, ValidationAgent
from app.config import settings
from app.schemas.contracts import BenchmarkCaseDefinition, BenchmarkCaseResult
from app.services.metrics_service import MetricsService

BenchmarkMode = Literal["rule_based", "llm", "llm_rag"]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class BenchmarkRunner:
    CASES_DIR = Path(__file__).resolve().parents[2] / "benchmark" / "cases"
    RESULTS_DIR = Path(__file__).resolve().parents[2] / "benchmark" / "results"

    def __init__(
        self,
        db: AsyncSession | None = None,
        cases_dir: Path | None = None,
        results_dir: Path | None = None,
    ) -> None:
        self.db = db
        self.cases_dir = cases_dir or self.CASES_DIR
        self.results_dir = results_dir or self.RESULTS_DIR

    def list_cases(self) -> list[BenchmarkCaseDefinition]:
        return self._load_cases()

    def get_available_cases(self) -> list[str]:
        """Return list of case IDs from benchmark/cases/ directory."""
        if not self.cases_dir.exists():
            return []
        return sorted(
            [
                file_path.stem.split("_", 1)[0]
                for file_path in self.cases_dir.glob("*.json")
                if not file_path.stem.startswith("_")
            ]
        )

    async def execute_case(
        self,
        case_id: str,
        mode: BenchmarkMode = "llm",
        db: AsyncSession | None = None,
    ) -> BenchmarkCaseResult:
        case = self._get_case(case_id)
        active_db = db or self.db
        _ = active_db
        started = time.perf_counter()
        planning_agent, codegen_agent, debugging_agent, optim_agent, rag_enabled = self._agents_for_mode(mode)
        validation_agent = ValidationAgent(mode="static")
        if hasattr(codegen_agent, "rag_enabled"):
            codegen_agent.rag_enabled = rag_enabled

        try:
            run_project_id = f"BM-{case.id}-{mode}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
            plan = await planning_agent.generate_plan(
                project_id=run_project_id,
                requirement_text=case.requirement,
                safety_constraints=list(case.safetyConstraints),
                performance_targets=self._default_targets(case.complexity),
                confirmed_outputs=list(case.expectedOutputs),
                domain=case.domain,
                complexity_tier=case.complexity,
            )
            artifact = await codegen_agent.generate_code(
                project_id=run_project_id,
                plan=plan,
                iteration=1,
            )
            validation = validation_agent.validate(
                project_id=run_project_id,
                artifact=artifact,
                plan=plan,
            )

            repair_iterations = 0
            while validation.status != "VERIFIED" and repair_iterations < settings.max_iter:
                debug = await debugging_agent.debug(
                    project_id=run_project_id,
                    plan=plan,
                    artifact=artifact,
                    validation=validation,
                    iteration=repair_iterations + 1,
                )
                if debug.status != "PATCH_ADVICE_GENERATED":
                    break
                artifact = await codegen_agent.generate_code(
                    project_id=run_project_id,
                    plan=plan,
                    patch_advice=debug.patchAdvice,
                    suggested_regeneration_prompt=debug.suggestedRegenerationPrompt,
                    iteration=artifact.iteration + 1,
                )
                validation = validation_agent.validate(
                    project_id=run_project_id,
                    artifact=artifact,
                    plan=plan,
                )
                repair_iterations += 1

            final_artifact = artifact
            if validation.status == "VERIFIED":
                optimization = await optim_agent.optimize(
                    project_id=run_project_id,
                    artifact=artifact,
                    plan=plan,
                    validation=validation,
                    repair_loop_report=None,
                )
                if optimization.status in {"OPTIMIZED", "NO_CHANGES", "ROLLED_BACK"}:
                    final_artifact = optimization.optimizedCode

            metrics = MetricsService.calculate(final_artifact.source)
            result = BenchmarkCaseResult(
                caseId=case.id,
                mode=mode,
                domain=case.domain,
                verified=validation.status == "VERIFIED",
                validationStatus=validation.status,
                repairIterations=repair_iterations,
                generationTimeMs=int((time.perf_counter() - started) * 1000),
                metrics=metrics,
                ragSourcesUsed=self._rag_sources(final_artifact),
                llmProvider=(final_artifact.metadata.llmProvider or plan.llmProvider or None),
                llmModel=(final_artifact.metadata.llmModel or plan.llmModel or None),
                generatedCode=final_artifact.source,
                error=None,
            )
            self._persist_result(result)
            return result
        except Exception as exc:
            result = BenchmarkCaseResult(
                caseId=case.id,
                mode=mode,
                domain=case.domain,
                verified=False,
                validationStatus=None,
                repairIterations=0,
                generationTimeMs=int((time.perf_counter() - started) * 1000),
                metrics=MetricsService.calculate("PROGRAM BENCHMARK_FAILED\nEND_PROGRAM"),
                ragSourcesUsed=[],
                llmProvider=None,
                llmModel=None,
                generatedCode="",
                error=str(exc),
            )
            self._persist_result(result)
            return result

    async def run_comparison(
        self,
        case_id: str,
        db: AsyncSession | None = None,
    ) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for mode in ["rule_based", "llm", "llm_rag"]:
            try:
                result = await self.execute_case(
                    case_id=case_id,
                    mode=mode,  # type: ignore[arg-type]
                    db=db,
                )
                results[mode] = result.model_dump()
            except Exception as exc:  # pragma: no cover
                results[mode] = {"error": str(exc), "mode": mode}
        return {
            "caseId": case_id,
            "results": results,
            "comparison": self._compute_comparison(results),
        }

    def _compute_comparison(self, results: dict[str, Any]) -> dict[str, Any]:
        baseline = results.get("rule_based", {}) or {}
        llm_r = results.get("llm", {}) or {}
        rag_r = results.get("llm_rag", {}) or {}

        def delta(a: dict[str, Any], b: dict[str, Any], key: str) -> float:
            av = a.get("metrics", {}).get(key, 0) or 0
            bv = b.get("metrics", {}).get(key, 0) or 0
            return round(float(bv) - float(av), 2)

        return {
            "llmVsBaseline": {
                "locDelta": delta(baseline, llm_r, "loc"),
                "ccDelta": delta(baseline, llm_r, "cyclomaticComplexity"),
                "miDelta": delta(baseline, llm_r, "maintainabilityIndex"),
                "scanDelta": delta(baseline, llm_r, "estimatedScanTimeMs"),
                "repairIterations": llm_r.get("repairIterations", 0),
                "verified": llm_r.get("verified", False),
            },
            "ragVsLlm": {
                "locDelta": delta(llm_r, rag_r, "loc"),
                "ccDelta": delta(llm_r, rag_r, "cyclomaticComplexity"),
                "miDelta": delta(llm_r, rag_r, "maintainabilityIndex"),
                "scanDelta": delta(llm_r, rag_r, "estimatedScanTimeMs"),
                "repairIterations": rag_r.get("repairIterations", 0),
                "verified": rag_r.get("verified", False),
            },
            "ragVsBaseline": {
                "locDelta": delta(baseline, rag_r, "loc"),
                "ccDelta": delta(baseline, rag_r, "cyclomaticComplexity"),
                "miDelta": delta(baseline, rag_r, "maintainabilityIndex"),
                "scanDelta": delta(baseline, rag_r, "estimatedScanTimeMs"),
                "repairIterations": rag_r.get("repairIterations", 0),
                "verified": rag_r.get("verified", False),
            },
        }

    def list_persisted_results(self) -> dict[str, dict[str, list[dict[str, Any]]]]:
        grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for payload in self._load_result_payloads():
            case_id = str(payload.get("caseId", "unknown"))
            mode = str(payload.get("mode", "unknown"))
            grouped.setdefault(case_id, {}).setdefault(mode, []).append(payload)
        return grouped

    def summary(self) -> dict[str, Any]:
        payloads = self._load_result_payloads()
        by_mode: dict[BenchmarkMode, dict[str, float]] = {
            "rule_based": {"loc": 0.0, "cc": 0.0, "verified": 0.0, "repairs": 0.0, "count": 0.0},
            "llm": {"loc": 0.0, "cc": 0.0, "verified": 0.0, "repairs": 0.0, "count": 0.0},
            "llm_rag": {"loc": 0.0, "cc": 0.0, "verified": 0.0, "repairs": 0.0, "count": 0.0},
        }
        cases_map: dict[str, dict[str, Any]] = {}
        case_lookup = self._case_lookup()
        for payload in payloads:
            mode = payload.get("mode")
            if mode not in by_mode:
                continue
            metrics = payload.get("metrics", {})
            by_mode[mode]["loc"] += float(metrics.get("loc", 0) or 0)
            by_mode[mode]["cc"] += float(metrics.get("cyclomaticComplexity", 0) or 0)
            by_mode[mode]["verified"] += 1.0 if payload.get("verified") else 0.0
            by_mode[mode]["repairs"] += float(payload.get("repairIterations", 0) or 0)
            by_mode[mode]["count"] += 1.0
            case_id = str(payload.get("caseId", "unknown"))
            cases_map.setdefault(case_id, {"id": case_id, "name": case_id, "results": {}})
            cases_map[case_id]["results"][mode] = payload
            definition = case_lookup.get(case_id)
            if definition is not None:
                cases_map[case_id]["name"] = definition.name

        by_mode_summary: dict[str, Any] = {}
        for mode, stats in by_mode.items():
            count = stats["count"] or 1.0
            by_mode_summary[mode] = {
                "avgLoc": round(stats["loc"] / count, 3),
                "avgCC": round(stats["cc"] / count, 3),
                "verificationRate": round((stats["verified"] / count) * 100, 2),
                "avgRepairIterations": round(stats["repairs"] / count, 3),
            }

        ranked = sorted(
            [
                (
                    mode,
                    by_mode_summary[mode]["verificationRate"],
                    by_mode_summary[mode]["avgCC"],
                    by_mode_summary[mode]["avgLoc"],
                )
                for mode in ["rule_based", "llm", "llm_rag"]
            ],
            key=lambda item: (-item[1], item[2], item[3]),
        )
        best_mode = ranked[0][0] if payloads else "none"
        return {
            "totalRuns": len(payloads),
            "byMode": by_mode_summary,
            "bestMode": best_mode,
            "cases": sorted(cases_map.values(), key=lambda item: item["id"]),
        }

    async def run_suite(self, db: AsyncSession | None = None) -> dict[str, Any]:
        suite_results: list[dict[str, Any]] = []
        for case in self._load_cases():
            suite_results.append(await self.run_comparison(case.id, db=db))
        return {
            "runId": f"benchmark-suite-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "completedAt": utc_now(),
            "totalCases": len(suite_results),
            "totalRuns": len(suite_results) * 3,
            "cases": suite_results,
            "summary": self.summary(),
        }

    def _agents_for_mode(
        self,
        mode: BenchmarkMode,
    ) -> tuple[PlanningAgent, CodeGenerationAgent, DebuggingAgent, OptimizationAgent, bool]:
        if mode == "rule_based":
            return (
                PlanningAgent(mode="rule_based"),
                CodeGenerationAgent(mode="template_based"),
                DebuggingAgent(mode="rule_based"),
                OptimizationAgent(mode="static"),
                False,
            )
        if mode == "llm":
            return (
                PlanningAgent(mode="llm"),
                CodeGenerationAgent(mode="llm"),
                DebuggingAgent(mode="llm"),
                OptimizationAgent(mode="llm"),
                False,
            )
        if mode == "llm_rag":
            return (
                PlanningAgent(mode="llm"),
                CodeGenerationAgent(mode="llm"),
                DebuggingAgent(mode="llm"),
                OptimizationAgent(mode="llm"),
                True,
            )
        raise ValueError(f"Unsupported benchmark mode: {mode}")

    @staticmethod
    def _rag_sources(artifact: Any) -> list[str]:
        rag_sources = getattr(getattr(artifact, "metadata", None), "ragSources", None) or []
        return [source.name for source in rag_sources if getattr(source, "name", None)]

    def _get_case(self, case_id: str) -> BenchmarkCaseDefinition:
        lookup = self._case_lookup()
        normalized = case_id.strip()
        if normalized in lookup:
            return lookup[normalized]
        raise ValueError(f"Benchmark case '{case_id}' was not found.")

    def _case_lookup(self) -> dict[str, BenchmarkCaseDefinition]:
        return {case.id: case for case in self._load_cases()}

    def _persist_result(self, result: BenchmarkCaseResult) -> None:
        self.results_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = self.results_dir / f"{result.caseId}_{result.mode}_{timestamp}.json"
        with target.open("w", encoding="utf-8") as handle:
            json.dump(result.model_dump(), handle, indent=2)

    def _load_result_payloads(self) -> list[dict[str, Any]]:
        if not self.results_dir.exists():
            return []
        payloads: list[dict[str, Any]] = []
        for file_path in sorted(self.results_dir.glob("*.json")):
            try:
                with file_path.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                if isinstance(payload, dict):
                    payloads.append(payload)
            except Exception:
                continue
        return payloads

    def _load_cases(self) -> list[BenchmarkCaseDefinition]:
        case_files = sorted(self.cases_dir.glob("*.json"))
        cases: list[BenchmarkCaseDefinition] = []
        for file_path in case_files:
            with file_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            cases.append(BenchmarkCaseDefinition.model_validate(payload))
        cases.sort(key=lambda case: case.id)
        return cases

    @staticmethod
    def _default_targets(complexity: Literal["simple", "medium", "complex"]) -> dict[str, int]:
        defaults = {
            "simple": {
                "maxScanTimeMs": 4,
                "maxCyclomaticComplexity": 6,
                "minMaintainabilityIndex": 78,
                "maxIterations": 3,
            },
            "medium": {
                "maxScanTimeMs": 6,
                "maxCyclomaticComplexity": 9,
                "minMaintainabilityIndex": 74,
                "maxIterations": 5,
            },
            "complex": {
                "maxScanTimeMs": 10,
                "maxCyclomaticComplexity": 12,
                "minMaintainabilityIndex": 70,
                "maxIterations": 7,
            },
        }
        return defaults.get(complexity, defaults["medium"])

import type {
  BenchmarkCaseCatalogItem,
  BenchmarkCaseResult,
  BenchmarkComparisonResult,
  BenchmarkMode,
  BenchmarkSuiteRunResponse,
  BenchmarkSummaryResponse
} from "@/lib/api-contracts";
import { API_ENDPOINTS } from "@/lib/api-contracts";
import { benchmarkCases } from "@/lib/mock-data";

import { isMockApiEnabled } from "./config";
import { apiRequest } from "./fetch-transport";
import { mockResolve } from "./mock-transport";

const BENCHMARK_TIMEOUT_MS = 180_000;

export async function getBenchmarkCases(): Promise<BenchmarkCaseCatalogItem[]> {
  if (!isMockApiEnabled()) {
    return apiRequest<BenchmarkCaseCatalogItem[]>(API_ENDPOINTS.getBenchmarkCases);
  }

  return mockResolve(
    benchmarkCases.slice(0, 5).map((item, index) => ({
      id: `B00${index + 1}`,
      name: item.name,
      domain: item.domain,
      complexity: item.complexity.toLowerCase() as "simple" | "medium" | "complex",
      requirement: `${item.name} deterministic benchmark requirement.`,
      safetyConstraints: ["Deterministic safety constraint"],
      expectedInputs: [],
      expectedOutputs: [],
      expectedProperties: [{ id: `B00${index + 1}-P1`, description: `${item.name} expected property.` }]
    }))
  );
}

export async function runBenchmarkCase(caseId: string, mode: BenchmarkMode): Promise<BenchmarkCaseResult> {
  if (!isMockApiEnabled()) {
    return apiRequest<BenchmarkCaseResult, { caseId: string; mode: BenchmarkMode }>(API_ENDPOINTS.runBenchmarks, {
      method: "POST",
      body: { caseId, mode },
      timeoutMs: BENCHMARK_TIMEOUT_MS
    });
  }
  return mockResolve(mockCaseResult(caseId, mode));
}

export async function compareBenchmarkModes(caseId: string): Promise<BenchmarkComparisonResult> {
  if (!isMockApiEnabled()) {
    return apiRequest<BenchmarkComparisonResult, { caseId: string }>(API_ENDPOINTS.compareBenchmarks, {
      method: "POST",
      body: { caseId },
      timeoutMs: BENCHMARK_TIMEOUT_MS
    });
  }
  const baseline = mockCaseResult(caseId, "rule_based");
  const llm = mockCaseResult(caseId, "llm");
  const rag = mockCaseResult(caseId, "llm_rag");
  const delta = (a: BenchmarkCaseResult, b: BenchmarkCaseResult) => ({
    locDelta: Number((b.metrics.loc - a.metrics.loc).toFixed(2)),
    ccDelta: Number((b.metrics.cyclomaticComplexity - a.metrics.cyclomaticComplexity).toFixed(2)),
    miDelta: Number((b.metrics.maintainabilityIndex - a.metrics.maintainabilityIndex).toFixed(2)),
    scanDelta: Number((b.metrics.estimatedScanTimeMs - a.metrics.estimatedScanTimeMs).toFixed(2)),
    repairIterations: b.repairIterations,
    verified: b.verified
  });
  return mockResolve({
    caseId,
    results: {
      rule_based: baseline,
      llm,
      llm_rag: rag
    },
    comparison: {
      llmVsBaseline: delta(baseline, llm),
      ragVsLlm: delta(llm, rag),
      ragVsBaseline: delta(baseline, rag)
    }
  });
}

export async function runBenchmarkSuite(): Promise<BenchmarkSuiteRunResponse> {
  if (!isMockApiEnabled()) {
    const payload = await apiRequest<unknown>(API_ENDPOINTS.runBenchmarkSuite, {
      method: "POST",
      timeoutMs: BENCHMARK_TIMEOUT_MS
    });
    return normalizeSuiteResponse(payload);
  }
  const cases = benchmarkCases.slice(0, 5).map((_, index) => {
    const caseId = `B00${index + 1}`;
    return {
      caseId,
      results: {
        rule_based: mockCaseResult(caseId, "rule_based"),
        llm: mockCaseResult(caseId, "llm"),
        llm_rag: mockCaseResult(caseId, "llm_rag")
      },
      comparison: {
        llmVsBaseline: { locDelta: -20, ccDelta: -6, miDelta: 14, scanDelta: 8080, repairIterations: 2, verified: true },
        ragVsLlm: { locDelta: -4, ccDelta: -1, miDelta: 3, scanDelta: 900, repairIterations: 1, verified: true },
        ragVsBaseline: { locDelta: -24, ccDelta: -7, miDelta: 17, scanDelta: 8980, repairIterations: 1, verified: true }
      }
    };
  });
  return mockResolve({
    runId: "mock-benchmark-suite",
    completedAt: "2026-05-23T18:00:00Z",
    totalCases: 5,
    totalRuns: 15,
    cases,
    summary: mockSummary()
  });
}

function normalizeSuiteResponse(payload: unknown): BenchmarkSuiteRunResponse {
  if (isBenchmarkSuiteRunResponse(payload)) {
    return payload;
  }

  const normalizedCases = toSuiteCasesFromRunSuitePayload(payload);
  const summary = buildSummaryFromCases(normalizedCases);
  return {
    runId: `suite-${Date.now()}`,
    completedAt: new Date().toISOString(),
    totalCases: normalizedCases.length,
    totalRuns: normalizedCases.length * 3,
    cases: normalizedCases,
    summary
  };
}

function isBenchmarkSuiteRunResponse(payload: unknown): payload is BenchmarkSuiteRunResponse {
  if (!payload || typeof payload !== "object") return false;
  const candidate = payload as Partial<BenchmarkSuiteRunResponse>;
  return Array.isArray(candidate.cases) && !!candidate.summary && typeof candidate.totalRuns === "number";
}

function toSuiteCasesFromRunSuitePayload(payload: unknown): BenchmarkComparisonResult[] {
  if (!payload || typeof payload !== "object") return [];
  const rows = (payload as { results?: unknown }).results;
  if (!Array.isArray(rows)) return [];

  return rows.map((row, idx) => {
    const caseId = (row as { caseId?: string }).caseId ?? `case-${idx}`;
    const results = ((row as { results?: Record<string, unknown> }).results ?? {}) as Record<string, unknown>;
    return {
      caseId,
      results: {
        rule_based: toResultOrError(results.rule_based, "rule_based"),
        llm: toResultOrError(results.llm, "llm"),
        llm_rag: toResultOrError(results.llm_rag, "llm_rag")
      },
      comparison: buildComparisonFromResults(
        toBenchmarkCaseResult(results.rule_based),
        toBenchmarkCaseResult(results.llm),
        toBenchmarkCaseResult(results.llm_rag)
      )
    };
  });
}

function toResultOrError(value: unknown, mode: BenchmarkMode): BenchmarkCaseResult | { error: string; mode?: string } {
  const resolved = toBenchmarkCaseResult(value);
  if (resolved) return resolved;
  return { error: (value as { error?: string })?.error ?? "Run failed.", mode };
}

function toBenchmarkCaseResult(value: unknown): BenchmarkCaseResult | null {
  if (!value || typeof value !== "object") return null;
  if (!("caseId" in value)) return null;
  return value as BenchmarkCaseResult;
}

function buildComparisonFromResults(
  baseline: BenchmarkCaseResult | null,
  llm: BenchmarkCaseResult | null,
  rag: BenchmarkCaseResult | null
) {
  const delta = (a: BenchmarkCaseResult | null, b: BenchmarkCaseResult | null) => ({
    locDelta: (b?.metrics.loc ?? 0) - (a?.metrics.loc ?? 0),
    ccDelta: (b?.metrics.cyclomaticComplexity ?? 0) - (a?.metrics.cyclomaticComplexity ?? 0),
    miDelta: (b?.metrics.maintainabilityIndex ?? 0) - (a?.metrics.maintainabilityIndex ?? 0),
    scanDelta: (b?.metrics.estimatedScanTimeMs ?? 0) - (a?.metrics.estimatedScanTimeMs ?? 0),
    repairIterations: b?.repairIterations ?? 0,
    verified: b?.verified ?? false
  });

  return {
    llmVsBaseline: delta(baseline, llm),
    ragVsLlm: delta(llm, rag),
    ragVsBaseline: delta(baseline, rag)
  };
}

function buildSummaryFromCases(cases: BenchmarkComparisonResult[]): BenchmarkSummaryResponse {
  const stats = {
    rule_based: { loc: 0, cc: 0, verified: 0, repairs: 0, count: 0 },
    llm: { loc: 0, cc: 0, verified: 0, repairs: 0, count: 0 },
    llm_rag: { loc: 0, cc: 0, verified: 0, repairs: 0, count: 0 }
  };

  for (const item of cases) {
    for (const mode of ["rule_based", "llm", "llm_rag"] as const) {
      const result = toBenchmarkCaseResult(item.results[mode]);
      if (!result) continue;
      stats[mode].loc += result.metrics.loc;
      stats[mode].cc += result.metrics.cyclomaticComplexity;
      stats[mode].verified += result.verified ? 1 : 0;
      stats[mode].repairs += result.repairIterations;
      stats[mode].count += 1;
    }
  }

  const byMode = {
    rule_based: summarizeMode(stats.rule_based),
    llm: summarizeMode(stats.llm),
    llm_rag: summarizeMode(stats.llm_rag)
  };

  const ranked: BenchmarkMode[] = ["rule_based", "llm", "llm_rag"];
  ranked.sort((a, b) => {
    const ver = byMode[b].verificationRate - byMode[a].verificationRate;
    if (ver !== 0) return ver;
    const cc = byMode[a].avgCC - byMode[b].avgCC;
    if (cc !== 0) return cc;
    return byMode[a].avgLoc - byMode[b].avgLoc;
  });

  return {
    totalRuns: stats.rule_based.count + stats.llm.count + stats.llm_rag.count,
    byMode,
    bestMode: cases.length ? ranked[0] : "none",
    cases: cases.map((item) => ({ id: item.caseId, name: item.caseId, results: item.results }))
  };
}

function summarizeMode(input: { loc: number; cc: number; verified: number; repairs: number; count: number }) {
  const count = input.count || 1;
  return {
    avgLoc: Number((input.loc / count).toFixed(3)),
    avgCC: Number((input.cc / count).toFixed(3)),
    verificationRate: Number(((input.verified / count) * 100).toFixed(2)),
    avgRepairIterations: Number((input.repairs / count).toFixed(3))
  };
}

export async function getBenchmarkResults() {
  if (!isMockApiEnabled()) {
    return apiRequest<Record<string, Record<string, BenchmarkCaseResult[]>>>(API_ENDPOINTS.getBenchmarkResults);
  }
  return mockResolve({});
}

export async function getBenchmarkSummary(): Promise<BenchmarkSummaryResponse> {
  if (!isMockApiEnabled()) {
    return apiRequest<BenchmarkSummaryResponse>(API_ENDPOINTS.getBenchmarkSummary);
  }
  return mockResolve(mockSummary());
}

function mockCaseResult(caseId: string, mode: BenchmarkMode): BenchmarkCaseResult {
  const baseline = {
    loc: 85,
    cyclomaticComplexity: 14,
    maintainabilityIndex: 42,
    estimatedScanTimeMs: 120
  };
  const modifier =
    mode === "rule_based"
      ? { loc: 0, cc: 0, mi: 0, scan: 0, repair: 0, verified: true, time: 120 }
      : mode === "llm"
        ? { loc: -23, cc: -6, mi: 26, scan: 8080, repair: 2, verified: true, time: 8200 }
        : { loc: -27, cc: -7, mi: 30, scan: 8980, repair: 1, verified: true, time: 9100 };
  return {
    caseId,
    mode,
    domain: "Mock Domain",
    verified: modifier.verified,
    validationStatus: modifier.verified ? "CHECKS_PASSED" : "FORMAL_VIOLATION",
    repairIterations: modifier.repair,
    generationTimeMs: modifier.time,
    metrics: {
      loc: baseline.loc + modifier.loc,
      cyclomaticComplexity: baseline.cyclomaticComplexity + modifier.cc,
      maintainabilityIndex: baseline.maintainabilityIndex + modifier.mi,
      estimatedScanTimeMs: baseline.estimatedScanTimeMs + modifier.scan
    },
    ragSourcesUsed: mode === "llm_rag" ? ["motor_fault_latch", "safe_state_pattern"] : [],
    llmProvider: mode === "rule_based" ? null : "mock-provider",
    llmModel: mode === "rule_based" ? null : "mock-model",
    generatedCode: "PROGRAM Mock\nEND_PROGRAM",
    error: null
  };
}

function mockSummary(): BenchmarkSummaryResponse {
  return {
    totalRuns: 15,
    byMode: {
      rule_based: { avgLoc: 85, avgCC: 14, verificationRate: 100, avgRepairIterations: 0 },
      llm: { avgLoc: 62, avgCC: 8, verificationRate: 100, avgRepairIterations: 2 },
      llm_rag: { avgLoc: 58, avgCC: 7, verificationRate: 100, avgRepairIterations: 1 }
    },
    bestMode: "llm_rag",
    cases: []
  };
}

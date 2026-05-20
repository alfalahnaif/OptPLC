import type { BenchmarkCase, FinalReport } from "@/lib/api-contracts";
import {
  benchmarkCases,
  currentProject,
  metricsCards,
  planObject,
  requirement
} from "@/lib/mock-data";

import { mockResolve } from "./mock-transport";
import { getMetricsReport, optimizeCode } from "./optimization-client";
import { validateCode } from "./validation-client";

export type ReportPageData = {
  currentProject: typeof currentProject;
  metricsCards: typeof metricsCards;
  planObject: typeof planObject;
  requirement: typeof requirement;
};

export type BenchmarkSuiteData = {
  benchmarkCases: typeof benchmarkCases;
};

export async function getReport(projectId: string): Promise<FinalReport> {
  return mockResolve({
    projectId,
    reportId: `${projectId}-final-report`,
    generatedAt: "2026-05-17T09:43:10Z",
    summary: "Verified and optimized IEC 61131-3 Structured Text report.",
    validation: await validateCode(projectId),
    optimization: await optimizeCode(projectId),
    metrics: await getMetricsReport(projectId)
  });
}

export async function getReportPageData(projectId: string): Promise<ReportPageData> {
  const project = { ...currentProject, id: projectId };
  return mockResolve({
    currentProject: project,
    metricsCards,
    planObject: { ...planObject, projectId },
    requirement
  });
}

export async function runBenchmarks(): Promise<BenchmarkCase[]> {
  return mockResolve(
    benchmarkCases.map((test) => ({
      id: test.id,
      name: test.name,
      domain: test.domain,
      complexity: test.complexity.toLowerCase() as "simple" | "medium" | "complex",
      status: test.status === "passed" || test.status === "warning" ? test.status : "pending",
      runtimeMs: Number.parseFloat(test.time) * 1000,
      optimizationGainPercent: Number.parseFloat(test.gain)
    }))
  );
}

export async function getBenchmarkSuiteData(): Promise<BenchmarkSuiteData> {
  return mockResolve({
    benchmarkCases
  });
}

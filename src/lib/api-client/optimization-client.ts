import type { CodeArtifact, MetricsReport, OptimizationReport, StructuredTextMetrics } from "@/lib/api-contracts";
import { API_ENDPOINTS, projectEndpoint } from "@/lib/api-contracts";
import {
  generatedStructuredText,
  optimizationPasses,
  optimizedStructuredText
} from "@/lib/mock-data";

import { ApiError, apiRequest } from "./fetch-transport";
import { isMockApiEnabled } from "./config";
import { mockResolve } from "./mock-transport";

export type OptimizationPageData = {
  report: OptimizationReport;
};

export type MetricsPageData = {
  report: MetricsReport;
  metricsCards: Array<{ label: string; before: number; after: number; delta: string; suffix: string }>;
  comparisonData: Array<{ metric: string; before: number; after: number }>;
  qualityRadar: Array<{ subject: string; before: number; after: number }>;
};

const optimizationReportCache = new Map<string, OptimizationReport>();

export async function optimizeCode(projectId: string): Promise<OptimizationReport> {
  if (!isMockApiEnabled()) {
    let report: OptimizationReport;
    try {
      report = await apiRequest<OptimizationReport>(projectEndpoint(API_ENDPOINTS.optimizeCode, projectId), {
        method: "POST",
        timeoutMs: 120000
      });
    } catch (error) {
      if (error instanceof ApiError && error.code === "timeout") {
        throw new Error("Optimization timed out after 2 minutes. Try again.");
      }
      throw error;
    }
    optimizationReportCache.set(projectId, report);
    return report;
  }

  const report = mockOptimizationReport(projectId);
  optimizationReportCache.set(projectId, report);
  return mockResolve(report);
}

export function getCachedOptimizationReport(projectId: string): OptimizationReport | undefined {
  return optimizationReportCache.get(projectId);
}

export async function getOptimizationPageData(projectId: string): Promise<OptimizationPageData | null> {
  if (!isMockApiEnabled()) {
    let report: OptimizationReport | null = null;
    try {
      report = await apiRequest<OptimizationReport>(projectEndpoint(API_ENDPOINTS.getOptimization, projectId));
    } catch (error) {
      if (!(error instanceof ApiError && error.status === 404)) {
        throw error;
      }
    }
    if (!report) return null;
    return mockResolve({
      report
    });
  }
  return mockResolve({
    report: await optimizeCode(projectId)
  });
}

function mockOptimizationReport(projectId: string): OptimizationReport {
  const beforeMetrics: StructuredTextMetrics = {
    loc: 47,
    cyclomaticComplexity: 9,
    maintainabilityIndex: 68,
    estimatedScanTimeMs: 4.1
  };
  const afterMetrics: StructuredTextMetrics = {
    loc: 33,
    cyclomaticComplexity: 4,
    maintainabilityIndex: 89,
    estimatedScanTimeMs: 2.4
  };
  const originalCode = codeArtifact({
    projectId,
    artifactId: `${projectId}-code-iter-2`,
    source: generatedStructuredText,
    iteration: 2,
    generator: "mock-codegen.v1",
    metrics: beforeMetrics,
    filename: "motor_controller.st"
  });
  const optimizedCode = codeArtifact({
    projectId,
    artifactId: `${projectId}-code-optimized-3`,
    source: optimizedStructuredText,
    iteration: 3,
    generator: "mock-optimizer.v1",
    metrics: afterMetrics,
    filename: "motor_controller_optimized.st"
  });

  return {
    projectId,
    sourceArtifactId: originalCode.artifactId,
    optimizedArtifactId: optimizedCode.artifactId,
    status: "OPTIMIZED",
    optimizer: "mock-optimizer.v1",
    originalCode,
    optimizedCode,
    passes: optimizationPasses.map((pass) => ({
      name: pass.name,
      status: "applied",
      summary: pass.description,
      accepted: true,
      revalidationStatus: "CHECKS_PASSED",
      beforeMetrics: {
        loc: pass.loc[0],
        cyclomaticComplexity: pass.cc[0],
        maintainabilityIndex: beforeMetrics.maintainabilityIndex,
        estimatedScanTimeMs: beforeMetrics.estimatedScanTimeMs
      },
      afterMetrics: {
        loc: pass.loc[1],
        cyclomaticComplexity: pass.cc[1],
        maintainabilityIndex: afterMetrics.maintainabilityIndex,
        estimatedScanTimeMs: afterMetrics.estimatedScanTimeMs
      }
    })),
    beforeMetrics,
    afterMetrics,
    metricsDelta: {
      loc: afterMetrics.loc - beforeMetrics.loc,
      cyclomaticComplexity: afterMetrics.cyclomaticComplexity - beforeMetrics.cyclomaticComplexity,
      maintainabilityIndex: afterMetrics.maintainabilityIndex - beforeMetrics.maintainabilityIndex,
      estimatedScanTimeMs: Number((afterMetrics.estimatedScanTimeMs - beforeMetrics.estimatedScanTimeMs).toFixed(1)),
      locReductionPercent: 29.8,
      cyclomaticReductionPercent: 55.6,
      maintainabilityGainPercent: 30.9,
      scanTimeReductionPercent: 41.5
    },
    revalidationStatus: "CHECKS_PASSED",
    rollbackEvents: [],
    createdAt: "2026-05-17T09:43:08Z",
    summary: "Static optimizer applied 3 pass(es); every accepted pass revalidated successfully.",
    revalidated: true
  };
}

function codeArtifact({
  projectId,
  artifactId,
  source,
  iteration,
  generator,
  metrics,
  filename
}: {
  projectId: string;
  artifactId: string;
  source: string;
  iteration: number;
  generator: string;
  metrics: StructuredTextMetrics;
  filename: string;
}): CodeArtifact {
  return {
    projectId,
    artifactId,
    language: "structured-text",
    filename,
    source,
    iteration,
    generatedAt: "2026-05-17T09:43:08Z",
    metrics: {
      loc: metrics.loc,
      cyclomaticComplexity: metrics.cyclomaticComplexity,
      maintainabilityIndex: metrics.maintainabilityIndex
    },
    metadata: {
      generator,
      iecStandard: "IEC 61131-3",
      sourcePlanId: projectId,
      createdAt: "2026-05-17T09:43:08Z",
      iteration
    }
  };
}

export async function getMetricsReport(projectId: string): Promise<MetricsReport | null> {
  if (!isMockApiEnabled()) {
    try {
      return await apiRequest<MetricsReport>(projectEndpoint(API_ENDPOINTS.getMetrics, projectId));
    } catch (error) {
      if (error instanceof ApiError && (error.status === 400 || error.status === 404)) {
        return null;
      }
      throw error;
    }
  }

  return mockResolve(mockMetricsReport(projectId));
}

export async function getMetricsPageData(projectId: string): Promise<MetricsPageData | null> {
  const report = await getMetricsReport(projectId);
  if (!report) return null;
  return mockResolve({
    report,
    metricsCards: metricCardsFromReport(report),
    comparisonData: comparisonDataFromReport(report),
    qualityRadar: qualityRadarFromReport(report)
  });
}

function mockMetricsReport(projectId: string): MetricsReport {
  const optimization = getCachedOptimizationReport(projectId) ?? mockOptimizationReport(projectId);
  return {
    projectId,
    source: {
      selected: "optimized_code",
      generatedCode: optimization.originalCode.artifactId,
      repairedCode: `${projectId}-code-iter-2`,
      optimizedCode: optimization.optimizedArtifactId
    },
    beforeMetrics: optimization.beforeMetrics,
    afterMetrics: optimization.afterMetrics,
    metricsDelta: {
      locDelta: optimization.metricsDelta.loc,
      cyclomaticComplexityDelta: optimization.metricsDelta.cyclomaticComplexity,
      maintainabilityIndexDelta: optimization.metricsDelta.maintainabilityIndex,
      estimatedScanTimeDelta: optimization.metricsDelta.estimatedScanTimeMs,
      locReductionPercent: optimization.metricsDelta.locReductionPercent,
      complexityReductionPercent: optimization.metricsDelta.cyclomaticReductionPercent,
      maintainabilityImprovementPercent: optimization.metricsDelta.maintainabilityGainPercent,
      scanTimeReductionPercent: optimization.metricsDelta.scanTimeReductionPercent
    },
    history: [
      {
        label: "Generated code",
        source: "generated_code",
        artifactId: optimization.originalCode.artifactId,
        metrics: optimization.beforeMetrics,
        createdAt: optimization.originalCode.generatedAt
      },
      {
        label: "Optimized code",
        source: "optimized_code",
        artifactId: optimization.optimizedArtifactId,
        metrics: optimization.afterMetrics,
        createdAt: optimization.optimizedCode.generatedAt
      }
    ],
    latestValidationStatus: "CHECKS_PASSED",
    latestOptimizationStatus: optimization.status,
    createdAt: "2026-05-17T09:43:10Z",
    summary: "Metrics compare generated Structured Text with the optimized code artifact."
  };
}

function comparisonDataFromReport(report: MetricsReport) {
  return [
    { metric: "LOC", before: report.beforeMetrics.loc, after: report.afterMetrics.loc },
    { metric: "CC", before: report.beforeMetrics.cyclomaticComplexity, after: report.afterMetrics.cyclomaticComplexity },
    { metric: "MI / 100", before: report.beforeMetrics.maintainabilityIndex, after: report.afterMetrics.maintainabilityIndex },
    { metric: "Scan (ms x10)", before: Math.round(report.beforeMetrics.estimatedScanTimeMs * 10), after: Math.round(report.afterMetrics.estimatedScanTimeMs * 10) }
  ];
}

function metricCardsFromReport(report: MetricsReport) {
  return [
    {
      label: "Lines of code",
      before: report.beforeMetrics.loc,
      after: report.afterMetrics.loc,
      delta: formatSignedPercent(report.metricsDelta.locReductionPercent),
      suffix: ""
    },
    {
      label: "Cyclomatic complexity",
      before: report.beforeMetrics.cyclomaticComplexity,
      after: report.afterMetrics.cyclomaticComplexity,
      delta: formatSignedPercent(report.metricsDelta.complexityReductionPercent),
      suffix: ""
    },
    {
      label: "Maintainability index",
      before: report.beforeMetrics.maintainabilityIndex,
      after: report.afterMetrics.maintainabilityIndex,
      delta: `+${report.metricsDelta.maintainabilityImprovementPercent.toFixed(1)}%`,
      suffix: ""
    },
    {
      label: "Estimated scan time",
      before: round(report.beforeMetrics.estimatedScanTimeMs),
      after: round(report.afterMetrics.estimatedScanTimeMs),
      delta: formatSignedPercent(report.metricsDelta.scanTimeReductionPercent),
      suffix: " ms"
    }
  ];
}

function qualityRadarFromReport(report: MetricsReport) {
  const compactnessBefore = clampQuality(100 - report.beforeMetrics.loc);
  const compactnessAfter = clampQuality(100 - report.afterMetrics.loc);
  const simplicityBefore = clampQuality(100 - report.beforeMetrics.cyclomaticComplexity * 10);
  const simplicityAfter = clampQuality(100 - report.afterMetrics.cyclomaticComplexity * 10);
  const scanBefore = clampQuality(100 - report.beforeMetrics.estimatedScanTimeMs * 12);
  const scanAfter = clampQuality(100 - report.afterMetrics.estimatedScanTimeMs * 12);

  return [
    { subject: "Maintainability", before: report.beforeMetrics.maintainabilityIndex, after: report.afterMetrics.maintainabilityIndex },
    { subject: "Compactness", before: compactnessBefore, after: compactnessAfter },
    { subject: "Simplicity", before: simplicityBefore, after: simplicityAfter },
    { subject: "Scan time", before: scanBefore, after: scanAfter }
  ];
}

function clampQuality(value: number) {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function round(value: number) {
  return Math.round(value * 100) / 100;
}

function formatSignedPercent(value: number) {
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

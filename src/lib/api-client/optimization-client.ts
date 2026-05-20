import type { CodeArtifact, MetricsReport, OptimizationReport, StructuredTextMetrics } from "@/lib/api-contracts";
import { API_ENDPOINTS, projectEndpoint } from "@/lib/api-contracts";
import {
  generatedStructuredText,
  optimizationPasses,
  optimizedStructuredText
} from "@/lib/mock-data";

import { apiRequest } from "./fetch-transport";
import { isMockApiEnabled } from "./config";
import { mockResolve } from "./mock-transport";

export type OptimizationPageData = {
  report: OptimizationReport;
};

export type MetricsPageData = {
  report: MetricsReport;
  comparisonData: Array<{ metric: string; before: number; after: number }>;
  qualityRadar: Array<{ subject: string; before: number; after: number }>;
};

const optimizationReportCache = new Map<string, OptimizationReport>();

export async function optimizeCode(projectId: string): Promise<OptimizationReport> {
  if (!isMockApiEnabled()) {
    const report = await apiRequest<OptimizationReport>(projectEndpoint(API_ENDPOINTS.optimizeCode, projectId), {
      method: "POST"
    });
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

export async function getOptimizationPageData(projectId: string): Promise<OptimizationPageData> {
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
      revalidationStatus: "VERIFIED",
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
    revalidationStatus: "VERIFIED",
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

export async function getMetricsReport(projectId: string): Promise<MetricsReport> {
  if (!isMockApiEnabled()) {
    return apiRequest<MetricsReport>(projectEndpoint(API_ENDPOINTS.getMetrics, projectId));
  }

  return mockResolve(mockMetricsReport(projectId));
}

export async function getMetricsPageData(projectId: string): Promise<MetricsPageData> {
  const report = await getMetricsReport(projectId);
  return mockResolve({
    report,
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
    latestValidationStatus: "VERIFIED",
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

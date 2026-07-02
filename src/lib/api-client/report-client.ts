import type { FinalReport } from "@/lib/api-contracts";
import { API_ENDPOINTS, projectEndpoint } from "@/lib/api-contracts";

import { isMockApiEnabled } from "./config";
import { apiBlobRequest, apiRequest } from "./fetch-transport";
import { mockResolve } from "./mock-transport";
import { getMetricsReport, optimizeCode } from "./optimization-client";
import { getProject } from "./project-client";
import { generateCode, getPlanObject } from "./workflow-client";
import { validateCode } from "./validation-client";

export async function getFinalReport(projectId: string): Promise<FinalReport> {
  if (!isMockApiEnabled()) {
    return apiRequest<FinalReport>(projectEndpoint(API_ENDPOINTS.getReport, projectId));
  }

  const project = await getProject(projectId);
  const planObject = await getPlanObject(projectId);
  const codeArtifact = await generateCode(projectId);
  const validation = await validateCode(projectId);
  const optimization = await optimizeCode(projectId);
  const metrics = await getMetricsReport(projectId);
  const metricsReport = metrics ?? {
    projectId,
    source: {
      selected: "generated_code" as const,
      generatedCode: codeArtifact.artifactId
    },
    beforeMetrics: {
      loc: codeArtifact.metrics?.loc ?? 0,
      cyclomaticComplexity: codeArtifact.metrics?.cyclomaticComplexity ?? 0,
      maintainabilityIndex: codeArtifact.metrics?.maintainabilityIndex ?? 0,
      estimatedScanTimeMs: 0
    },
    afterMetrics: {
      loc: codeArtifact.metrics?.loc ?? 0,
      cyclomaticComplexity: codeArtifact.metrics?.cyclomaticComplexity ?? 0,
      maintainabilityIndex: codeArtifact.metrics?.maintainabilityIndex ?? 0,
      estimatedScanTimeMs: 0
    },
    metricsDelta: {
      locDelta: 0,
      cyclomaticComplexityDelta: 0,
      maintainabilityIndexDelta: 0,
      estimatedScanTimeDelta: 0,
      locReductionPercent: 0,
      complexityReductionPercent: 0,
      maintainabilityImprovementPercent: 0,
      scanTimeReductionPercent: 0
    },
    history: [],
    latestValidationStatus: validation.status,
    latestOptimizationStatus: optimization.status,
    createdAt: "2026-05-17T09:43:10Z",
    summary: "Metrics unavailable."
  };

  return mockResolve({
    projectId,
    reportId: `${projectId}-final-report`,
    generatedAt: "2026-05-17T09:43:10Z",
    summary: "Verified and optimized IEC 61131-3 Structured Text report.",
    validation,
    optimization,
    metrics: metricsReport,
    project,
    requirement: {
      projectId,
      text: "Control a three-phase conveyor motor with E-stop and overload protection.",
      safetyConstraints: [
        "Emergency stop must de-energize motor output in one scan.",
        "No automatic restart after safety trip."
      ],
      performanceTargets: {
        maxScanTimeMs: 8,
        maxCyclomaticComplexity: 10,
        minMaintainabilityIndex: 75,
        maxIterations: 5
      }
    },
    planObject,
    codeArtifact,
    debugging: null,
    repairLoop: null,
    validationSummary: validation.summary,
    debuggingSummary: "Debugging has not been run yet.",
    repairLoopSummary: "Repair loop has not been run yet.",
    optimizationSummary: optimization.summary,
    metricsSummary: metricsReport.summary,
    finalStatusSummary: `Project status is '${project.status}'. Validation status: ${validation.status}. Optimization status: ${optimization.status}.`,
    recommendations: ["Run debugging and repair loop only if future validation fails."],
    limitationsDisclaimer:
      "This report is generated from deterministic pipeline artifacts; PDF certificate export is future work."
  });
}

export const getReport = getFinalReport;

export async function exportReportJson(projectId: string): Promise<Blob> {
  if (!isMockApiEnabled()) {
    return apiBlobRequest(projectEndpoint(API_ENDPOINTS.exportReportJson, projectId));
  }

  const report = await getFinalReport(projectId);
  return new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
}

export async function exportReportMarkdown(projectId: string): Promise<Blob> {
  if (!isMockApiEnabled()) {
    return apiBlobRequest(projectEndpoint(API_ENDPOINTS.exportReportMarkdown, projectId));
  }

  const report = await getFinalReport(projectId);
  return new Blob([toReportMarkdown(report)], { type: "text/markdown" });
}

function toReportMarkdown(report: FinalReport): string {
  const requirementText = report.requirement?.text ?? "Not generated yet";
  const planSummary = report.planObject
    ? `Inputs: ${report.planObject.inputs.length} | Outputs: ${report.planObject.outputs.length} | Safety constraints: ${report.planObject.safetyConstraints.length}`
    : "Not generated yet";
  const codeSection = report.codeArtifact?.source ?? "Not generated yet";
  const debuggingSummary = report.debugging ? report.debuggingSummary : "Not generated yet";
  const repairLoopSummary = report.repairLoop ? report.repairLoopSummary : "Not generated yet";
  const optimizationSummary = report.optimization ? report.optimizationSummary : "Not generated yet";
  const metricsSummary = report.metrics ? report.metricsSummary : "Not generated yet";
  const recommendations = report.recommendations.length
    ? report.recommendations.map((item) => `- ${item}`).join("\n")
    : "- Not generated yet";

  return `# PLCForge Final Report - ${report.projectId}

Generated at: ${report.generatedAt}

## Project Metadata

- Project ID: ${report.project.id}
- Name: ${report.project.name}
- Domain: ${report.project.domain}
- Status: ${report.project.status}
- Standard: ${report.project.standard}
- Target Language: ${report.project.targetLanguage}

## Requirement

${requirementText}

## Plan Summary

${planSummary}

## Generated Code

\`\`\`iecst
${codeSection}
\`\`\`

## Validation Summary

${report.validationSummary}

## Debugging Summary

${debuggingSummary}

## Repair Loop Summary

${repairLoopSummary}

## Optimization Summary

${optimizationSummary}

## Metrics Summary

${metricsSummary}

## Final Status Summary

${report.finalStatusSummary}

## Recommendations

${recommendations}

## Limitations Disclaimer

${report.limitationsDisclaimer}
`;
}

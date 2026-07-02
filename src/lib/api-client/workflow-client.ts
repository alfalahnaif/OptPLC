import type { CodeArtifact, PlanObject, RepairLoopReport, WorkflowEvent } from "@/lib/api-contracts";
import { API_ENDPOINTS, projectEndpoint } from "@/lib/api-contracts";

import { cloneMock, mockResolve } from "./mock-transport";
import { isMockApiEnabled } from "./config";
import { ApiError, apiRequest } from "./fetch-transport";
import { getCachedRepairLoopReport } from "./validation-client";
import { getCachedOptimizationReport } from "./optimization-client";

type WorkflowMocks = Pick<
  typeof import("@/lib/mock-data"),
  "generatedStructuredText" | "planObject" | "sessionLog" | "workflowEvents"
>;

async function getWorkflowMocks(): Promise<WorkflowMocks> {
  const { generatedStructuredText, planObject, sessionLog, workflowEvents } = await import("@/lib/mock-data");
  return { generatedStructuredText, planObject, sessionLog, workflowEvents };
}

export type WorkflowMonitorData = {
  workflowEvents: WorkflowMocks["workflowEvents"];
  sessionLog: WorkflowMocks["sessionLog"];
  repairLoopReport?: RepairLoopReport;
};

export type CodePageData = {
  artifact: CodeArtifact;
  source: string;
  ragSources: string[];
  repairLoopReport?: RepairLoopReport;
  optimizationReport?: import("@/lib/api-contracts").OptimizationReport;
};

export async function createPlan(projectId: string): Promise<PlanObject> {
  if (!isMockApiEnabled()) {
    return apiRequest<PlanObject>(projectEndpoint(API_ENDPOINTS.createPlan, projectId), {
      method: "POST"
    });
  }

  const { planObject } = await getWorkflowMocks();
  const plan = cloneMock(planObject) as PlanObject;
  plan.projectId = projectId;
  return mockResolve(plan);
}

export const generatePlan = createPlan;

export async function getPlanObject(projectId: string): Promise<PlanObject | null> {
  if (!isMockApiEnabled()) {
    try {
      return await apiRequest<PlanObject>(projectEndpoint(API_ENDPOINTS.getPlan, projectId));
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) return null;
      throw error;
    }
  }
  const { planObject } = await getWorkflowMocks();
  const plan = cloneMock(planObject) as PlanObject;
  plan.projectId = projectId;
  return mockResolve(plan);
}

export async function getWorkflowEvents(projectId: string): Promise<WorkflowEvent[]> {
  const { workflowEvents } = await getWorkflowMocks();
  return mockResolve(
    workflowEvents.map((event, index) => ({
      id: `${projectId}-wf-${index + 1}`,
      projectId,
      agent: event.agent,
      status: event.status === "failed" ? "failed" : "completed",
      iteration: event.iter,
      inputSummary: event.input,
      outputSummary: event.output,
      durationMs: Number.parseFloat(event.duration) * 1000,
      createdAt: "2026-05-17T09:42:14Z"
    }))
  );
}

export async function getWorkflowMonitorData(projectId: string): Promise<WorkflowMonitorData> {
  const { sessionLog, workflowEvents } = await getWorkflowMocks();
  const repairLoopReport = getCachedRepairLoopReport(projectId);
  return mockResolve({
    workflowEvents,
    sessionLog,
    repairLoopReport
  });
}

export async function generateCode(projectId: string): Promise<CodeArtifact> {
  if (!isMockApiEnabled()) {
    return apiRequest<CodeArtifact>(projectEndpoint(API_ENDPOINTS.generateCode, projectId), {
      method: "POST"
    });
  }

  const { generatedStructuredText } = await getWorkflowMocks();
  return mockResolve({
    projectId,
    artifactId: `${projectId}-code-iter-2`,
    language: "structured-text",
    filename: "motor_controller.st",
    source: generatedStructuredText,
    iteration: 2,
    generatedAt: "2026-05-17T09:42:49Z",
    metrics: {
      loc: 47,
      cyclomaticComplexity: 9,
      maintainabilityIndex: 68
    },
    metadata: {
      generator: "mock-codegen.v1",
      iecStandard: "IEC 61131-3",
      sourcePlanId: projectId,
      createdAt: "2026-05-17T09:42:49Z",
      iteration: 2
    }
  });
}

export async function getCodePageData(projectId: string): Promise<CodePageData | null> {
  if (!isMockApiEnabled()) {
    let artifact: CodeArtifact | null = null;
    try {
      artifact = await apiRequest<CodeArtifact>(projectEndpoint(API_ENDPOINTS.getCode, projectId));
    } catch (error) {
      if (!(error instanceof ApiError && error.status === 404)) {
        throw error;
      }
    }
    if (!artifact) return null;
    return mockResolve({
      artifact,
      source: artifact.source,
      ragSources: [],
      repairLoopReport: undefined,
      optimizationReport: undefined
    });
  }

  const { generatedStructuredText } = await getWorkflowMocks();
  const repairLoopReport = getCachedRepairLoopReport(projectId);
  const optimizationReport = getCachedOptimizationReport(projectId);
  if (optimizationReport) {
    const artifact = optimizationReport.optimizedCode;
    return mockResolve({
      artifact,
      source: artifact.source,
      ragSources: [],
      repairLoopReport,
      optimizationReport
    });
  }
  if (repairLoopReport) {
    const artifact = repairLoopReport.finalCodeArtifact;
    return mockResolve({
      artifact,
      source: artifact.source,
      ragSources: [],
      repairLoopReport,
      optimizationReport
    });
  }

  return mockResolve({
    artifact: await generateCode(projectId),
    source: generatedStructuredText,
    ragSources: [
      "IEC 61131-3 Programming languages.pdf",
      "Beckhoff TwinCAT ST style guide.pdf",
      "Siemens SCL best practices.pdf",
      "Safety patterns - IEC 62061 motor.md"
    ],
    repairLoopReport,
    optimizationReport
  });
}

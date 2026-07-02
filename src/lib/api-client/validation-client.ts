import type { DebuggingReport, RepairLoopReport, ValidationReport } from "@/lib/api-contracts";
import { API_ENDPOINTS, projectEndpoint } from "@/lib/api-contracts";
import { requirement, validation } from "@/lib/mock-data";

import { isMockApiEnabled } from "./config";
import { ApiError, apiRequest } from "./fetch-transport";
import { mockResolve } from "./mock-transport";

export type ValidationPageData = {
  requirement: typeof requirement;
  validation: typeof validation;
  report: ValidationReport;
  repairLoopReport?: RepairLoopReport;
};

export type DebuggingPageData = {
  validation: typeof validation;
  report: DebuggingReport;
  repairLoopReport?: RepairLoopReport;
};

const repairLoopCache = new Map<string, RepairLoopReport>();

export async function validateCode(projectId: string): Promise<ValidationReport> {
  if (!isMockApiEnabled()) {
    return apiRequest<ValidationReport>(projectEndpoint(API_ENDPOINTS.validateCode, projectId), {
      method: "POST"
    });
  }

  return mockResolve(mockValidationReport(projectId));
}

function mockValidationReport(projectId: string): ValidationReport {
  const safetyResults = requirement.constraints.map((description, index) => ({
    id: `SC${index + 1}`,
    description,
    status: "passed" as const,
    details: null
  }));

  return {
    projectId,
    artifactId: `${projectId}-code-iter-2`,
    iteration: validation.iteration,
    status: "VERIFIED",
    syntaxPassed: true,
    formalPassed: true,
    solver: validation.solver,
    validator: "mock-validator.v1",
    checkedAt: "2026-05-17T14:09:51Z",
    summary: "Structured Text syntax and static safety checks passed.",
    syntaxErrors: [],
    formalErrors: [],
    safetyResults,
    properties: safetyResults,
    errors: [],
    counterexamples: [],
    counterexample: undefined
  };
}

export async function getValidationPageData(projectId: string): Promise<ValidationPageData | null> {
  const report = !isMockApiEnabled()
    ? await getValidationReport(projectId)
    : await validateCode(projectId);
  if (!report) return null;
  return mockResolve({
    requirement,
    validation,
    report,
    repairLoopReport: isMockApiEnabled() ? repairLoopCache.get(projectId) : undefined
  });
}

export async function debugCode(projectId: string): Promise<DebuggingReport> {
  if (!isMockApiEnabled()) {
    return apiRequest<DebuggingReport>(projectEndpoint(API_ENDPOINTS.debugCode, projectId), {
      method: "POST"
    });
  }

  return mockResolve({
    projectId,
    sourceArtifactId: `${projectId}-code-iter-1`,
    status: "PATCH_ADVICE_GENERATED",
    sourceValidationStatus: "FORMAL_VIOLATION",
    errorType: "unsafe_auto_restart",
    rootCause: "Missing latched fault state allowed auto-restart after E-stop recovery.",
    rootCauseSummary: "Missing latched fault state allowed auto-restart after E-stop recovery.",
    affectedCodeRegion: "Fault reset and run latch logic",
    patchAdvice: [
      "Introduce a latched Fault_State variable that survives E-stop recovery.",
      "Clear Fault_State only when Reset_PB is pressed and all fault sources are clear.",
      "Force Run_Cmd false whenever Fault_State is true.",
      "Map Fault_Lamp directly to the latched fault state."
    ],
    suggestedRegenerationPrompt: "Regenerate the motor controller with a latched Fault_State, explicit Reset_PB clearance, and Motor_Run gated by NOT Fault_State.",
    counterexampleSummary: "4 counterexample steps reported; motor re-energized after E-stop recovery without reset.",
    createdAt: "2026-05-17T09:42:44Z",
    debugger: "mock-debugger.v1",
    regeneratedArtifactId: `${projectId}-code-iter-2`
  });
}

export async function runRepairLoop(projectId: string): Promise<RepairLoopReport> {
  if (!isMockApiEnabled()) {
    const report = await apiRequest<RepairLoopReport>(projectEndpoint(API_ENDPOINTS.repairLoop, projectId), {
      method: "POST",
      timeoutMs: 120000
    });
    repairLoopCache.set(projectId, report);
    return report;
  }

  const report = mockRepairLoopReport(projectId);
  repairLoopCache.set(projectId, report);
  return mockResolve(report);
}

export function getCachedRepairLoopReport(projectId: string): RepairLoopReport | undefined {
  return repairLoopCache.get(projectId);
}

export async function getDebuggingPageData(projectId: string): Promise<DebuggingPageData | null> {
  const report = !isMockApiEnabled()
    ? await getDebuggingReport(projectId)
    : await debugCode(projectId);
  if (!report) return null;
  return mockResolve({
    validation,
    report,
    repairLoopReport: isMockApiEnabled() ? repairLoopCache.get(projectId) : undefined
  });
}

export async function getValidationReport(projectId: string): Promise<ValidationReport | null> {
  if (isMockApiEnabled()) {
    return validateCode(projectId);
  }
  try {
    return await apiRequest<ValidationReport>(projectEndpoint(API_ENDPOINTS.getValidation, projectId));
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export async function getDebuggingReport(projectId: string): Promise<DebuggingReport | null> {
  if (isMockApiEnabled()) {
    return debugCode(projectId);
  }
  try {
    return await apiRequest<DebuggingReport>(projectEndpoint(API_ENDPOINTS.getDebug, projectId));
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

function mockRepairLoopReport(projectId: string): RepairLoopReport {
  const finalValidation = mockValidationReport(projectId);
  const initialCode = {
    projectId,
    artifactId: `${projectId}-code-iter-1`,
    language: "structured-text" as const,
    filename: "motor_controller.st",
    source: "PROGRAM Motor_Controller\nEND_PROGRAM",
    iteration: 1,
    generatedAt: "2026-05-17T09:42:26Z",
    metrics: {
      loc: 38,
      cyclomaticComplexity: 8,
      maintainabilityIndex: 66
    },
    metadata: {
      generator: "mock-codegen.v1",
      iecStandard: "IEC 61131-3" as const,
      sourcePlanId: projectId,
      createdAt: "2026-05-17T09:42:26Z",
      iteration: 1
    }
  };
  const repairedCode = {
    ...initialCode,
    artifactId: `${projectId}-code-iter-2`,
    source: [
      "PROGRAM Motor_Controller",
      "VAR_INPUT",
      "    E_Stop : BOOL;",
      "    Overload : BOOL;",
      "    Reset_PB : BOOL;",
      "END_VAR",
      "VAR_OUTPUT",
      "    Motor_Run : BOOL;",
      "END_VAR",
      "VAR",
      "    Fault_State : BOOL;",
      "    Safety_OK : BOOL;",
      "END_VAR",
      "Safety_OK := E_Stop AND NOT Overload;",
      "Motor_Run := Safety_OK AND NOT Fault_State;",
      "END_PROGRAM"
    ].join("\n"),
    iteration: 2,
    generatedAt: "2026-05-17T09:42:49Z",
    metrics: {
      loc: 47,
      cyclomaticComplexity: 9,
      maintainabilityIndex: 68
    },
    metadata: {
      ...initialCode.metadata,
      generator: "template_based.repair.v1",
      createdAt: "2026-05-17T09:42:49Z",
      iteration: 2
    }
  };
  const debugReport = {
    projectId,
    sourceArtifactId: initialCode.artifactId,
    status: "PATCH_ADVICE_GENERATED" as const,
    sourceValidationStatus: "FORMAL_VIOLATION" as const,
    errorType: "unsafe_auto_restart",
    rootCause: "Missing latched fault state allowed auto-restart after E-stop recovery.",
    rootCauseSummary: "Missing latched fault state allowed auto-restart after E-stop recovery.",
    affectedCodeRegion: "Fault reset and run latch logic",
    patchAdvice: [
      "Introduce a latched Fault_State variable that survives E-stop recovery.",
      "Clear Fault_State only when Reset_PB is pressed and all fault sources are clear."
    ],
    suggestedRegenerationPrompt: "Regenerate the motor controller with a latched Fault_State and explicit Reset_PB clearance.",
    counterexampleSummary: "4 counterexample steps reported; motor re-energized after E-stop recovery without reset.",
    createdAt: "2026-05-17T09:42:44Z",
    debugger: "mock-debugger.v1",
    regeneratedArtifactId: repairedCode.artifactId
  };

  return {
    projectId,
    finalStatus: "VERIFIED",
    iterations: 2,
    finalCodeArtifact: repairedCode,
    finalValidationReport: finalValidation,
    debuggingReports: [debugReport],
    codeVersions: [initialCode, repairedCode],
    validationReports: [
      {
        ...finalValidation,
        artifactId: initialCode.artifactId,
        iteration: 1,
        status: "FORMAL_VIOLATION",
        syntaxPassed: true,
        formalPassed: false,
        summary: "Static safety checks found domain-specific violations.",
        formalErrors: ["Fault latching and Reset_PB handling are required to prevent auto-restart."],
        errors: ["Fault latching and Reset_PB handling are required to prevent auto-restart."],
        counterexamples: [{ step: 1, property: "MC-3", violation: "Unsafe auto-restart risk." }]
      },
      finalValidation
    ],
    summary: "Repair loop verified the code after 2 validation attempts and 1 debugging pass."
  };
}

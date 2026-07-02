import { afterEach, describe, expect, it, vi } from "vitest";

import type { CodeArtifact, CreateProjectRequest, DebuggingReport, PlanObject, Project, RepairLoopReport, RequirementInput, RequirementPayload, ValidationReport, WorkflowEvent } from "@/lib/api-contracts";
import {
  createProject,
  debugCode,
  generateCode,
  generatePlan,
  getHealth,
  getProject,
  getProjects,
  getRequirements,
  runRepairLoop,
  submitRequirements,
  validateCode
} from "@/lib/api-client";

describe("project API client transport selection", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("defaults to mock mode when the env flag is enabled", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "true");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await expect(getProjects()).resolves.toEqual(
      expect.arrayContaining([expect.objectContaining({ id: "PRJ-0421" })])
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("calls GET /api/projects when mock mode is disabled", async () => {
    const fetchMock = stubRealApi(projectsResponse());

    await expect(getProjects()).resolves.toEqual(projectsResponse());

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/projects",
      expect.objectContaining({ method: "GET" })
    );
  });

  it("calls GET /api/projects/{id} when mock mode is disabled", async () => {
    const fetchMock = stubRealApi(projectResponse("PRJ-0421"));

    await expect(getProject("PRJ-0421")).resolves.toMatchObject({ id: "PRJ-0421" });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/projects/PRJ-0421",
      expect.objectContaining({ method: "GET" })
    );
  });

  it("calls POST /api/projects when creating a project", async () => {
    const fetchMock = stubRealApi(projectResponse("PRJ-0500"), 201);
    const request: CreateProjectRequest = {
      name: "Mixer Control",
      description: "Agitator motor with permissive chain.",
      domain: "Motor Control",
      targetLanguage: "Structured Text",
      complexityTier: "medium"
    };

    await expect(createProject(request)).resolves.toMatchObject({ id: "PRJ-0500" });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/projects",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(request)
      })
    );
  });

  it("calls POST /api/projects/{id}/requirements for requirement submission", async () => {
    const event: WorkflowEvent = {
      id: "PRJ-0421-wf-planning-1",
      projectId: "PRJ-0421",
      agent: "Planning Agent",
      status: "completed",
      iteration: 1,
      inputSummary: "Requirement accepted",
      outputSummary: "Requirement envelope stored",
      durationMs: 4200,
      createdAt: "2026-05-17T09:42:18Z"
    };
    const fetchMock = stubRealApi(event);
    const request: RequirementInput = {
      projectId: "PRJ-0421",
      text: "Control motor with E-stop and overload latch.",
      safetyConstraints: ["No automatic restart"],
      performanceTargets: {
        maxScanTimeMs: 5,
        maxCyclomaticComplexity: 8,
        minMaintainabilityIndex: 75,
        maxIterations: 5
      }
    };

    await expect(submitRequirements(request)).resolves.toEqual(event);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/projects/PRJ-0421/requirements",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(request)
      })
    );
  });

  it("calls GET /api/projects/{id}/requirements for persisted requirements", async () => {
    const payload: RequirementPayload = {
      projectId: "PRJ-0421",
      text: "Persisted requirement",
      safetyConstraints: ["Constraint A"],
      performanceTargets: {
        maxScanTimeMs: 5,
        maxCyclomaticComplexity: 8,
        minMaintainabilityIndex: 75,
        maxIterations: 5
      },
      domain: "Motor Control",
      complexityTier: "medium",
      submittedAt: "2026-05-17T09:42:18Z",
      updatedAt: "2026-05-17T09:42:18Z"
    };
    const fetchMock = stubRealApi(payload);

    await expect(getRequirements("PRJ-0421")).resolves.toEqual(payload);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/projects/PRJ-0421/requirements",
      expect.objectContaining({ method: "GET" })
    );
  });

  it("maps GET /requirements 404 to null in real mode", async () => {
    const fetchMock = stubRealApi({ detail: "Requirements for project PRJ-0421 were not found." }, 404);

    await expect(getRequirements("PRJ-0421")).resolves.toBeNull();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/projects/PRJ-0421/requirements",
      expect.objectContaining({ method: "GET" })
    );
  });

  it("calls POST /api/projects/{id}/plan for plan generation", async () => {
    const plan: PlanObject = {
      projectId: "PRJ-0421",
      agent: "PlanningAgent/v1.4",
      generatedAt: "2026-05-17T09:42:18Z",
      inputs: [],
      outputs: [],
      logicRules: [],
      safetyConstraints: [],
      scope: {
        standard: "IEC 61131-3",
        edition: "3rd ed. (2013)",
        language: "Structured Text",
        runtime: "CODESYS / TwinCAT compatible"
      }
    };
    const fetchMock = stubRealApi(plan);

    await expect(generatePlan("PRJ-0421")).resolves.toEqual(plan);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/projects/PRJ-0421/plan",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("calls POST /api/projects/{id}/generate for code generation", async () => {
    const artifact = codeArtifact("PRJ-0421");
    const fetchMock = stubRealApi(artifact);

    await expect(generateCode("PRJ-0421")).resolves.toEqual(artifact);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/projects/PRJ-0421/generate",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("calls POST /api/projects/{id}/validate for code validation", async () => {
    const report = validationReport("PRJ-0421");
    const fetchMock = stubRealApi(report);

    await expect(validateCode("PRJ-0421")).resolves.toEqual(report);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/projects/PRJ-0421/validate",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("calls POST /api/projects/{id}/debug for debugging advice", async () => {
    const report = debuggingReport("PRJ-0421");
    const fetchMock = stubRealApi(report);

    await expect(debugCode("PRJ-0421")).resolves.toEqual(report);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/projects/PRJ-0421/debug",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("calls POST /api/projects/{id}/repair-loop for repair loop", async () => {
    const report = repairLoopReport("PRJ-0421");
    const fetchMock = stubRealApi(report);

    await expect(runRepairLoop("PRJ-0421")).resolves.toEqual(report);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/projects/PRJ-0421/repair-loop",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("calls GET /api/health when mock mode is disabled", async () => {
    const fetchMock = stubRealApi({
      status: "healthy",
      service: "plc-agent-optimizer-api",
      version: "0.1.0",
      timestamp: "2026-05-18T00:00:00Z"
    });

    await expect(getHealth()).resolves.toMatchObject({ status: "healthy" });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/health",
      expect.objectContaining({ method: "GET" })
    );
  });
});

function stubRealApi(payload: unknown, status = 200) {
  vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(payload), {
      status,
      headers: {
        "Content-Type": "application/json"
      }
    })
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function codeArtifact(projectId: string): CodeArtifact {
  return {
    projectId,
    artifactId: `${projectId}-code-iter-1`,
    language: "structured-text",
    filename: "plc_prj_0421_controller.st",
    source: "PROGRAM PLC_PRJ_0421_Controller\nEND_PROGRAM",
    iteration: 1,
    generatedAt: "2026-05-19T10:00:00Z",
    metrics: {
      loc: 2,
      cyclomaticComplexity: 1,
      maintainabilityIndex: 89
    },
    metadata: {
      generator: "template_based.v1",
      iecStandard: "IEC 61131-3",
      sourcePlanId: projectId,
      createdAt: "2026-05-19T10:00:00Z",
      iteration: 1
    }
  };
}

function projectsResponse(): Project[] {
  return [projectResponse("PRJ-0421")];
}

function projectResponse(id: string): Project {
  return {
    id,
    name: "Motor Control - Conveyor M-12",
    domain: "Motor Control",
    description: "Three-phase motor with E-stop and overload protection.",
    standard: "IEC 61131-3",
    targetLanguage: "Structured Text",
    status: "planned",
    createdAt: "2026-05-17T09:40:00Z",
    updatedAt: "2026-05-17T09:42:18Z"
  };
}

function validationReport(projectId: string): ValidationReport {
  return {
    projectId,
    artifactId: `${projectId}-code-iter-1`,
    iteration: 1,
    status: "VERIFIED",
    syntaxPassed: true,
    formalPassed: true,
    solver: "static.v1",
    validator: "static.v1",
    checkedAt: "2026-05-19T10:00:00Z",
    summary: "Structured Text syntax and static safety checks passed.",
    syntaxErrors: [],
    formalErrors: [],
    safetyResults: [
      {
        id: "MC-1",
        description: "Motor output must be forced FALSE when emergency stop is active",
        status: "passed",
        details: null
      }
    ],
    properties: [
      {
        id: "MC-1",
        description: "Motor output must be forced FALSE when emergency stop is active",
        status: "passed",
        details: null
      }
    ],
    errors: [],
    counterexamples: []
  };
}

function debuggingReport(projectId: string): DebuggingReport {
  return {
    projectId,
    sourceArtifactId: `${projectId}-code-iter-1`,
    status: "PATCH_ADVICE_GENERATED",
    sourceValidationStatus: "FORMAL_VIOLATION",
    errorType: "motor_safety_shutdown",
    rootCause: "Motor_Run is not visibly forced FALSE by the emergency stop path.",
    rootCauseSummary: "Motor_Run is not visibly forced FALSE by the emergency stop path.",
    affectedCodeRegion: "Motor_Run and safety latch logic",
    patchAdvice: ["Introduce a Safety_OK expression using E_Stop and Overload."],
    suggestedRegenerationPrompt: "Regenerate with Safety_OK gating Motor_Run.",
    counterexampleSummary: "1 counterexample step reported.",
    createdAt: "2026-05-19T10:00:00Z",
    debugger: "rule_based.v1"
  };
}

function repairLoopReport(projectId: string): RepairLoopReport {
  const artifact = codeArtifact(projectId);
  const validation = validationReport(projectId);
  const debugging = debuggingReport(projectId);

  return {
    projectId,
    finalStatus: "VERIFIED",
    iterations: 2,
    finalCodeArtifact: artifact,
    finalValidationReport: validation,
    debuggingReports: [debugging],
    codeVersions: [artifact],
    validationReports: [validation],
    summary: "Repair loop verified the code after 2 validation attempts and 1 debugging pass."
  };
}

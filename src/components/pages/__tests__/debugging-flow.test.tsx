import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DebuggingPage } from "@/components/pages/debugging-page";
import type { DebuggingReport } from "@/lib/api-contracts";

describe("Debugging frontend flow", () => {
  afterEach(() => {
    const routerPush = (globalThis as unknown as { __nextRouterPush?: ReturnType<typeof vi.fn> }).__nextRouterPush;
    routerPush?.mockReset();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("Debugging page renders PATCH_ADVICE_GENERATED in real mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    stubFetch(debuggingReport("PRJ-0421", "PATCH_ADVICE_GENERATED"));

    render(<DebuggingPage projectId="PRJ-0421" />);

    expect(await screen.findByText("Real Backend DebuggingReport")).toBeInTheDocument();
    expect((await screen.findAllByText("PATCH_ADVICE_GENERATED")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Motor_Run and safety latch logic")).toBeInTheDocument();
    expect(await screen.findByText("Introduce a Safety_OK expression using Emergency_Stop and Overload.")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Run Repair Loop" })).toBeInTheDocument();
  });

  it("RepairLoopReport renders final CHECKS_PASSED status", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/debug")) return Promise.resolve(jsonResponse(debuggingReport("PRJ-0421", "PATCH_ADVICE_GENERATED")));
      if (url.endsWith("/validation")) return Promise.resolve(jsonResponse(validationReport("PRJ-0421", "FORMAL_VIOLATION")));
      if (url.endsWith("/repair-loop")) return Promise.resolve(jsonResponse(repairLoopReport("PRJ-0421", "CHECKS_PASSED")));
      return Promise.resolve(jsonResponse({}, 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<DebuggingPage projectId="PRJ-0421" />);

    fireEvent.click(await screen.findByRole("button", { name: "Run Repair Loop" }));

    expect(await screen.findByText("Repair loop")).toBeInTheDocument();
    expect((await screen.findAllByText("CHECKS_PASSED")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Repair loop reached passing validation checks after 2 validation attempts and 1 debugging pass.")).toBeInTheDocument();
  });

  it("iteration limit status renders correctly", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/debug")) return Promise.resolve(jsonResponse(debuggingReport("PRJ-0421", "PATCH_ADVICE_GENERATED")));
      if (url.endsWith("/validation")) return Promise.resolve(jsonResponse(validationReport("PRJ-0421", "FORMAL_VIOLATION")));
      if (url.endsWith("/repair-loop")) return Promise.resolve(jsonResponse(repairLoopReport("PRJ-0421", "ITERATION_LIMIT_REACHED")));
      return Promise.resolve(jsonResponse({}, 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<DebuggingPage projectId="PRJ-0421" />);

    fireEvent.click(await screen.findByRole("button", { name: "Run Repair Loop" }));

    expect(await screen.findByText("ITERATION_LIMIT_REACHED")).toBeInTheDocument();
  });

  it("Debugging page renders NOT_REQUIRED for code that passed the checks", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    stubFetch(debuggingReport("PRJ-0421", "NOT_REQUIRED", {
      sourceValidationStatus: "CHECKS_PASSED",
      errorType: "none",
      rootCauseSummary: "No debugging required because the validation checks passed.",
      rootCause: "No debugging required because the validation checks passed.",
      affectedCodeRegion: "None",
      patchAdvice: ["No patch advice is required. Continue to optimization when ready."],
      counterexampleSummary: null
    }));

    render(<DebuggingPage projectId="PRJ-0421" />);

    expect(await screen.findByText("NOT_REQUIRED")).toBeInTheDocument();
    expect(await screen.findByText("No debugging required. The latest validation checks passed.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Run Repair Loop" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Replay failure/i })).not.toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /Run Optimization/ })).toBeInTheDocument();
  });

  it("Debugging page renders CANNOT_DEBUG for timeout", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    stubFetch(debuggingReport("PRJ-0421", "CANNOT_DEBUG", {
      sourceValidationStatus: "TIMEOUT",
      errorType: "verification_timeout",
      rootCauseSummary: "The validator timed out before producing a concrete syntax or safety failure.",
      rootCause: "The validator timed out before producing a concrete syntax or safety failure.",
      affectedCodeRegion: "Verification scope",
      patchAdvice: ["Reduce code complexity before retrying validation."]
    }));

    render(<DebuggingPage projectId="PRJ-0421" />);

    expect(await screen.findByText("CANNOT_DEBUG")).toBeInTheDocument();
    expect(await screen.findByText("Reduce code complexity before retrying validation.")).toBeInTheDocument();
  });

  it("missing DebuggingReport shows guidance state", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/debug")) return Promise.resolve(jsonResponse({ detail: "Debugging report for project PRJ-0421 was not found." }, 404));
      if (url.endsWith("/validation")) return Promise.resolve(jsonResponse({ detail: "Validation report for project PRJ-0421 was not found." }, 404));
      return Promise.resolve(jsonResponse({}, 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<DebuggingPage projectId="PRJ-0421" />);

    expect(await screen.findByText("Run validation before requesting debugging advice.")).toBeInTheDocument();
  });

  it("missing DebuggingReport with CHECKS_PASSED validation shows no debugging required path", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/debug")) return Promise.resolve(jsonResponse({ detail: "Debugging report for project PRJ-0421 was not found." }, 404));
      if (url.endsWith("/validation")) return Promise.resolve(jsonResponse(validationReport("PRJ-0421", "CHECKS_PASSED")));
      return Promise.resolve(jsonResponse({}, 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<DebuggingPage projectId="PRJ-0421" />);

    expect(await screen.findByText("No debugging required. The latest validation checks passed.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Run Repair Loop" })).not.toBeInTheDocument();
  });

  it("NOT_REQUIRED path runs optimization before navigation", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/debug")) return Promise.resolve(jsonResponse(debuggingReport("PRJ-0421", "NOT_REQUIRED", { sourceValidationStatus: "CHECKS_PASSED" })));
      if (url.endsWith("/validation")) return Promise.resolve(jsonResponse(validationReport("PRJ-0421", "CHECKS_PASSED")));
      if (url.endsWith("/optimize") && init?.method === "POST") return Promise.resolve(jsonResponse(optimizationReport("PRJ-0421")));
      return Promise.resolve(jsonResponse({}, 404));
    });
    vi.stubGlobal("fetch", fetchMock);
    const routerPush = (globalThis as unknown as { __nextRouterPush: ReturnType<typeof vi.fn> }).__nextRouterPush;

    render(<DebuggingPage projectId="PRJ-0421" />);
    fireEvent.click(await screen.findByRole("button", { name: /Run Optimization/ }));

    expect(await screen.findByText(/Running optimization|No debugging required/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/projects/PRJ-0421/optimize",
      expect.objectContaining({ method: "POST" })
    );
    expect(routerPush).toHaveBeenCalledWith("/projects/PRJ-0421/optimization");
  });

  it("mock mode still renders mock debugging report", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "true");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<DebuggingPage projectId="PRJ-0421" />);

    expect(await screen.findByText("Mock Debugger")).toBeInTheDocument();
    expect(await screen.findByText("Missing latched fault state allowed auto-restart after E-stop recovery.")).toBeInTheDocument();
    expect(await screen.findByText("Introduce a latched Fault_State variable that survives E-stop recovery.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

function stubFetch(payload: unknown, status = 200) {
  const fetchMock = vi.fn().mockResolvedValue(jsonResponse(payload, status));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json"
    }
  });
}

function debuggingReport(
  projectId: string,
  status: DebuggingReport["status"],
  overrides: Partial<DebuggingReport> = {}
): DebuggingReport {
  return {
    projectId,
    sourceArtifactId: `${projectId}-code-iter-1`,
    status,
    sourceValidationStatus: "FORMAL_VIOLATION",
    errorType: "motor_safety_shutdown",
    rootCause: "Motor_Run is not visibly forced FALSE by the emergency stop path.",
    rootCauseSummary: "Motor_Run is not visibly forced FALSE by the emergency stop path.",
    affectedCodeRegion: "Motor_Run and safety latch logic",
    patchAdvice: ["Introduce a Safety_OK expression using Emergency_Stop and Overload."],
    suggestedRegenerationPrompt: "Regenerate with Safety_OK gating Motor_Run.",
    counterexampleSummary: "1 counterexample step reported.",
    createdAt: "2026-05-19T10:00:00Z",
    debugger: "rule_based.v1",
    ...overrides
  };
}

function repairLoopReport(projectId: string, finalStatus: "CHECKS_PASSED" | "FAILED" | "ITERATION_LIMIT_REACHED") {
  const finalCodeArtifact = {
    projectId,
    artifactId: `${projectId}-code-iter-2`,
    language: "structured-text" as const,
    filename: "plc_prj_0421_controller.st",
    source: "PROGRAM PLC_PRJ_0421_Controller\nEND_PROGRAM",
    iteration: 2,
    generatedAt: "2026-05-19T10:00:00Z",
    metrics: {
      loc: 2,
      cyclomaticComplexity: 1,
      maintainabilityIndex: 89
    },
    metadata: {
      generator: "template_based.repair.v1",
      iecStandard: "IEC 61131-3" as const,
      sourcePlanId: projectId,
      createdAt: "2026-05-19T10:00:00Z",
      iteration: 2
    }
  };
  const finalValidationReport = {
    projectId,
    artifactId: finalCodeArtifact.artifactId,
    iteration: 2,
    status: finalStatus === "CHECKS_PASSED" ? "CHECKS_PASSED" as const : "FORMAL_VIOLATION" as const,
    syntaxPassed: true,
    formalPassed: finalStatus === "CHECKS_PASSED",
    solver: "static.v1",
    validator: "static.v1",
    checkedAt: "2026-05-19T10:00:00Z",
    summary: "Structured Text syntax and static safety checks passed.",
    syntaxErrors: [],
    formalErrors: [],
    safetyResults: [],
    properties: [],
    errors: [],
    counterexamples: []
  };

  return {
    projectId,
    finalStatus,
    iterations: 2,
    finalCodeArtifact,
    finalValidationReport,
    debuggingReports: [debuggingReport(projectId, "PATCH_ADVICE_GENERATED")],
    codeVersions: [finalCodeArtifact],
    validationReports: [finalValidationReport],
    summary:
      finalStatus === "CHECKS_PASSED"
        ? "Repair loop reached passing validation checks after 2 validation attempts and 1 debugging pass."
        : "Repair loop stopped after reaching the iteration limit of 2 validation attempt(s)."
  };
}

function validationReport(projectId: string, status: "CHECKS_PASSED" | "FORMAL_VIOLATION") {
  return {
    projectId,
    artifactId: `${projectId}-code-iter-1`,
    iteration: 1,
    status,
    syntaxPassed: true,
    formalPassed: status === "CHECKS_PASSED",
    solver: "static.v1",
    validator: "static.v1",
    checkedAt: "2026-05-19T10:00:00Z",
    summary: "Validation summary.",
    syntaxErrors: [],
    formalErrors: status === "CHECKS_PASSED" ? [] : ["Formal violation."],
    safetyResults: [],
    properties: [],
    errors: [],
    counterexamples: []
  };
}

function optimizationReport(projectId: string) {
  return {
    projectId,
    sourceArtifactId: `${projectId}-code-iter-1`,
    optimizedArtifactId: `${projectId}-code-optimized-2`,
    status: "OPTIMIZED",
    optimizer: "static.v1",
    originalCode: {
      projectId,
      artifactId: `${projectId}-code-iter-1`,
      language: "structured-text",
      filename: "a.st",
      source: "PROGRAM A\nEND_PROGRAM",
      iteration: 1,
      generatedAt: "2026-05-19T10:00:00Z",
      metrics: { loc: 2, cyclomaticComplexity: 1, maintainabilityIndex: 90 },
      metadata: { generator: "template_based.v1", iecStandard: "IEC 61131-3", sourcePlanId: projectId, createdAt: "2026-05-19T10:00:00Z", iteration: 1 }
    },
    optimizedCode: {
      projectId,
      artifactId: `${projectId}-code-optimized-2`,
      language: "structured-text",
      filename: "b.st",
      source: "PROGRAM B\nEND_PROGRAM",
      iteration: 2,
      generatedAt: "2026-05-19T10:00:00Z",
      metrics: { loc: 2, cyclomaticComplexity: 1, maintainabilityIndex: 90 },
      metadata: { generator: "static_optimizer.v1", iecStandard: "IEC 61131-3", sourcePlanId: projectId, createdAt: "2026-05-19T10:00:00Z", iteration: 2 }
    },
    passes: [],
    beforeMetrics: { loc: 2, cyclomaticComplexity: 1, maintainabilityIndex: 90, estimatedScanTimeMs: 1 },
    afterMetrics: { loc: 2, cyclomaticComplexity: 1, maintainabilityIndex: 90, estimatedScanTimeMs: 1 },
    metricsDelta: { loc: 0, cyclomaticComplexity: 0, maintainabilityIndex: 0, estimatedScanTimeMs: 0, locReductionPercent: 0, cyclomaticReductionPercent: 0, maintainabilityGainPercent: 0, scanTimeReductionPercent: 0 },
    revalidationStatus: "CHECKS_PASSED",
    rollbackEvents: [],
    createdAt: "2026-05-19T10:00:00Z",
    summary: "optimized",
    revalidated: true
  };
}

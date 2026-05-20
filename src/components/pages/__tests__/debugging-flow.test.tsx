import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DebuggingPage } from "@/components/pages/debugging-page";
import type { DebuggingReport } from "@/lib/api-contracts";

describe("Debugging frontend flow", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("Debugging page renders PATCH_ADVICE_GENERATED in real mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    stubFetch(debuggingReport("PRJ-0421", "PATCH_ADVICE_GENERATED"));

    render(<DebuggingPage projectId="PRJ-0421" />);

    expect(await screen.findByText("Real Rule-Based Debugger")).toBeInTheDocument();
    expect((await screen.findAllByText("PATCH_ADVICE_GENERATED")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Motor_Run and safety latch logic")).toBeInTheDocument();
    expect(await screen.findByText("Introduce a Safety_OK expression using E_Stop and Overload.")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Run Repair Loop" })).toBeInTheDocument();
  });

  it("RepairLoopReport renders final VERIFIED status", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(debuggingReport("PRJ-0421", "PATCH_ADVICE_GENERATED")))
      .mockResolvedValueOnce(jsonResponse(repairLoopReport("PRJ-0421", "VERIFIED")));
    vi.stubGlobal("fetch", fetchMock);

    render(<DebuggingPage projectId="PRJ-0421" />);

    fireEvent.click(await screen.findByRole("button", { name: "Run Repair Loop" }));

    expect(await screen.findByText("Repair loop")).toBeInTheDocument();
    expect((await screen.findAllByText("VERIFIED")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Repair loop verified the code after 2 validation attempts and 1 debugging pass.")).toBeInTheDocument();
  });

  it("iteration limit status renders correctly", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(debuggingReport("PRJ-0421", "PATCH_ADVICE_GENERATED")))
      .mockResolvedValueOnce(jsonResponse(repairLoopReport("PRJ-0421", "ITERATION_LIMIT_REACHED")));
    vi.stubGlobal("fetch", fetchMock);

    render(<DebuggingPage projectId="PRJ-0421" />);

    fireEvent.click(await screen.findByRole("button", { name: "Run Repair Loop" }));

    expect(await screen.findByText("ITERATION_LIMIT_REACHED")).toBeInTheDocument();
  });

  it("Debugging page renders NOT_REQUIRED for verified code", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    stubFetch(debuggingReport("PRJ-0421", "NOT_REQUIRED", {
      sourceValidationStatus: "VERIFIED",
      errorType: "none",
      rootCauseSummary: "No debugging required because the code is verified.",
      rootCause: "No debugging required because the code is verified.",
      affectedCodeRegion: "None",
      patchAdvice: ["No patch advice is required. Continue to optimization when ready."],
      counterexampleSummary: null
    }));

    render(<DebuggingPage projectId="PRJ-0421" />);

    expect(await screen.findByText("NOT_REQUIRED")).toBeInTheDocument();
    expect(await screen.findByText("No debugging required because the code is verified.")).toBeInTheDocument();
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

  it("missing ValidationReport backend error is displayed with guidance", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    stubFetch({ detail: "ValidationReport must be generated before debugging." }, 400);

    render(<DebuggingPage projectId="PRJ-0421" />);

    expect(await screen.findByText("Debugging feedback unavailable")).toBeInTheDocument();
    expect(await screen.findByText("Run validation before requesting debugging advice.")).toBeInTheDocument();
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
    patchAdvice: ["Introduce a Safety_OK expression using E_Stop and Overload."],
    suggestedRegenerationPrompt: "Regenerate with Safety_OK gating Motor_Run.",
    counterexampleSummary: "1 counterexample step reported.",
    createdAt: "2026-05-19T10:00:00Z",
    debugger: "rule_based.v1",
    ...overrides
  };
}

function repairLoopReport(projectId: string, finalStatus: "VERIFIED" | "FAILED" | "ITERATION_LIMIT_REACHED") {
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
    status: finalStatus === "VERIFIED" ? "VERIFIED" as const : "FORMAL_VIOLATION" as const,
    syntaxPassed: true,
    formalPassed: finalStatus === "VERIFIED",
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
      finalStatus === "VERIFIED"
        ? "Repair loop verified the code after 2 validation attempts and 1 debugging pass."
        : "Repair loop stopped after reaching the iteration limit of 2 validation attempt(s)."
  };
}

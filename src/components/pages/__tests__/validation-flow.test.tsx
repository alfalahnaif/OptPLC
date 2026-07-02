import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ValidationPage } from "@/components/pages/validation-page";
import type { ValidationReport } from "@/lib/api-contracts";

describe("Validation frontend flow", () => {
  afterEach(() => {
    const routerPush = (globalThis as unknown as { __nextRouterPush?: ReturnType<typeof vi.fn> }).__nextRouterPush;
    routerPush?.mockReset();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("Validation page renders backend VERIFIED result in real mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/projects/PRJ-0421/validation")) {
        return Promise.resolve(jsonResponse(validationReport("PRJ-0421", "VERIFIED")));
      }
      if (url.endsWith("/api/projects/PRJ-0421/optimize") && init?.method === "POST") {
        return Promise.resolve(jsonResponse(mockOptimizationReport("PRJ-0421")));
      }
      return Promise.resolve(jsonResponse({ detail: "Unhandled request" }, 500));
    });
    vi.stubGlobal("fetch", fetchMock);
    const routerPush = (globalThis as unknown as { __nextRouterPush: ReturnType<typeof vi.fn> }).__nextRouterPush;

    render(<ValidationPage projectId="PRJ-0421" />);

    expect(await screen.findByText("Real Backend ValidationReport")).toBeInTheDocument();
    expect((await screen.findAllByText("VERIFIED")).length).toBeGreaterThan(0);
    expect(await screen.findByText("All properties hold")).toBeInTheDocument();
    expect((await screen.findAllByText("static.v1")).length).toBeGreaterThan(0);
    fireEvent.click(await screen.findByRole("button", { name: /Continue to Optimization/ }));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://api.test/api/projects/PRJ-0421/optimize",
        expect.objectContaining({ method: "POST" })
      );
      expect(routerPush).toHaveBeenCalledWith("/projects/PRJ-0421/optimization");
    });
  });

  it("Validation page renders backend SYNTAX_ERROR result", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/projects/PRJ-0421/validation")) {
        return Promise.resolve(jsonResponse(validationReport("PRJ-0421", "SYNTAX_ERROR", {
          syntaxErrors: ["END_PROGRAM is required for PROGRAM blocks."]
        })));
      }
      if (url.endsWith("/api/projects/PRJ-0421/debug") && init?.method === "POST") {
        return Promise.resolve(jsonResponse(mockDebuggingReport("PRJ-0421")));
      }
      return Promise.resolve(jsonResponse({ detail: "Unhandled request" }, 500));
    });
    vi.stubGlobal("fetch", fetchMock);
    const routerPush = (globalThis as unknown as { __nextRouterPush: ReturnType<typeof vi.fn> }).__nextRouterPush;

    render(<ValidationPage projectId="PRJ-0421" />);

    expect(await screen.findByText("SYNTAX_ERROR")).toBeInTheDocument();
    expect(await screen.findByText("Syntax checks failed")).toBeInTheDocument();
    expect(await screen.findByText("END_PROGRAM is required for PROGRAM blocks.")).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: /Open Debugging Advice/ }));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://api.test/api/projects/PRJ-0421/debug",
        expect.objectContaining({ method: "POST" })
      );
      expect(routerPush).toHaveBeenCalledWith("/projects/PRJ-0421/debugging");
    });
  });

  it("Validation page renders backend FORMAL_VIOLATION result", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    stubFetch(validationReport("PRJ-0421", "FORMAL_VIOLATION", {
      formalErrors: ["Motor_Run is not visibly gated by Emergency_Stop or the safety/fault state."]
    }));

    render(<ValidationPage projectId="PRJ-0421" />);

    expect((await screen.findAllByText("FORMAL_VIOLATION")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Safety checks failed")).toBeInTheDocument();
    expect((await screen.findAllByText("Motor_Run is not visibly gated by Emergency_Stop or the safety/fault state.")).length).toBeGreaterThan(0);
  });

  it("Continue to Optimization shows error and does not navigate on optimize failure", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/projects/PRJ-0421/validation")) {
        return Promise.resolve(jsonResponse(validationReport("PRJ-0421", "VERIFIED")));
      }
      if (url.endsWith("/api/projects/PRJ-0421/optimize") && init?.method === "POST") {
        return Promise.resolve(jsonResponse({ detail: "Code must be verified before optimization. Run validation or repair loop first." }, 400));
      }
      return Promise.resolve(jsonResponse({ detail: "Unhandled request" }, 500));
    });
    vi.stubGlobal("fetch", fetchMock);
    const routerPush = (globalThis as unknown as { __nextRouterPush: ReturnType<typeof vi.fn> }).__nextRouterPush;

    render(<ValidationPage projectId="PRJ-0421" />);
    fireEvent.click(await screen.findByRole("button", { name: /Continue to Optimization/ }));

    expect(await screen.findByText(/Code must be verified before optimization/)).toBeInTheDocument();
    expect(routerPush).not.toHaveBeenCalled();
  });

  it("missing ValidationReport shows guidance state", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    stubFetch({ detail: "Validation report for project PRJ-0421 was not found." }, 404);

    render(<ValidationPage projectId="PRJ-0421" />);

    expect(await screen.findByText("No validation report")).toBeInTheDocument();
    expect(await screen.findByText("Run validation from the Generated Code page before viewing results.")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /Run validation now/i })).toBeInTheDocument();
  });

  it("Run validation now creates report and renders persisted result", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    let validated = false;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/projects/PRJ-0421/validation")) {
        if (!validated) {
          return Promise.resolve(jsonResponse({ detail: "Validation report for project PRJ-0421 was not found." }, 404));
        }
        return Promise.resolve(jsonResponse(validationReport("PRJ-0421", "VERIFIED")));
      }
      if (url.endsWith("/api/projects/PRJ-0421/validate") && init?.method === "POST") {
        validated = true;
        return Promise.resolve(jsonResponse(validationReport("PRJ-0421", "VERIFIED")));
      }
      return Promise.resolve(jsonResponse({ detail: `Unhandled request: ${init?.method ?? "GET"} ${url}` }, 500));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<ValidationPage projectId="PRJ-0421" />);

    expect(await screen.findByText("No validation report")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Run validation now/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://api.test/api/projects/PRJ-0421/validate",
        expect.objectContaining({ method: "POST" })
      );
    });
    expect(await screen.findByText("All properties hold")).toBeInTheDocument();
    expect(await screen.findByText("Real Backend ValidationReport")).toBeInTheDocument();
  });

  it("mock mode still renders mock validation result", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "true");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<ValidationPage projectId="PRJ-0421" />);

    expect(await screen.findByText("Mock Validator")).toBeInTheDocument();
    expect((await screen.findAllByText("VERIFIED")).length).toBeGreaterThan(0);
    expect(await screen.findByText("All properties hold")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

function stubFetch(payload: unknown, status = 200) {
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

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json"
    }
  });
}

function validationReport(
  projectId: string,
  status: ValidationReport["status"],
  overrides: Partial<ValidationReport> = {}
): ValidationReport {
  const syntaxPassed = status !== "SYNTAX_ERROR";
  const formalPassed = status === "VERIFIED";
  const failedDetails =
    status === "FORMAL_VIOLATION"
      ? "Motor_Run is not visibly gated by Emergency_Stop or the safety/fault state."
      : null;
  const safetyResults: ValidationReport["safetyResults"] = [
    {
      id: "MC-1",
      description: "Motor output must be forced FALSE when emergency stop is active",
      status: status === "FORMAL_VIOLATION" ? "failed" : "passed",
      details: failedDetails
    }
  ];

  return {
    projectId,
    artifactId: `${projectId}-code-iter-1`,
    iteration: 1,
    status,
    syntaxPassed,
    formalPassed,
    solver: "static.v1",
    validator: "static.v1",
    checkedAt: "2026-05-19T10:00:00Z",
    summary:
      status === "VERIFIED"
        ? "Structured Text syntax and static safety checks passed."
        : status === "SYNTAX_ERROR"
          ? "Structured Text syntax/static checks failed."
          : "Static safety checks found domain-specific violations.",
    syntaxErrors: status === "SYNTAX_ERROR" ? ["END_PROGRAM is required for PROGRAM blocks."] : [],
    formalErrors: status === "FORMAL_VIOLATION" ? [failedDetails ?? "Safety check failed."] : [],
    safetyResults,
    properties: safetyResults,
    errors: [],
    counterexamples: status === "FORMAL_VIOLATION" ? [{ step: 1, property: "MC-1", violation: failedDetails ?? "" }] : [],
    ...overrides
  };
}

function mockOptimizationReport(projectId: string) {
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
    revalidationStatus: "VERIFIED",
    rollbackEvents: [],
    createdAt: "2026-05-19T10:00:00Z",
    summary: "optimized",
    revalidated: true
  };
}

function mockDebuggingReport(projectId: string) {
  return {
    projectId,
    sourceArtifactId: `${projectId}-code-iter-1`,
    status: "PATCH_ADVICE_GENERATED",
    sourceValidationStatus: "SYNTAX_ERROR",
    errorType: "missing_end_pou",
    rootCause: "missing end program",
    rootCauseSummary: "missing end program",
    affectedCodeRegion: "POU footer",
    patchAdvice: ["Add END_PROGRAM"],
    suggestedRegenerationPrompt: "fix",
    counterexampleSummary: null,
    createdAt: "2026-05-19T10:00:00Z",
    debugger: "rule_based.v1"
  };
}

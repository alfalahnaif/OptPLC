import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CodeArtifact, ValidationReport } from "@/lib/api-contracts";
import { CodePage } from "@/components/pages/code-page";

describe("Code Generation frontend flow", () => {
  afterEach(() => {
    const routerPush = (globalThis as unknown as { __nextRouterPush?: ReturnType<typeof vi.fn> }).__nextRouterPush;
    routerPush?.mockReset();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("Code page renders backend-generated Structured Text in real mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    stubFetch(artifact("PRJ-0421"));

    render(<CodePage projectId="PRJ-0421" />);

    expect(await screen.findByText("Real Backend CodeArtifact")).toBeInTheDocument();
    expect(await screen.findByText("Generated IEC 61131-3 Structured Text")).toBeInTheDocument();
    expect(await screen.findByText(/PROGRAM PLC_PRJ_0421_Controller/)).toBeInTheDocument();
    expect(await screen.findByText(/Motor_Run := Run_Cmd/)).toBeInTheDocument();
    expect(await screen.findByText("template_based.v1")).toBeInTheDocument();
    expect(await screen.findAllByText("Code metadata")).toHaveLength(3);
  });

  it("missing code artifact shows guidance state", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    stubFetch({ detail: "Code artifact for project PRJ-0421 was not found." }, 404);

    render(<CodePage projectId="PRJ-0421" />);

    expect(await screen.findByText("No code artifact")).toBeInTheDocument();
    expect(await screen.findByText("Generate Structured Text code before viewing this page.")).toBeInTheDocument();
  });

  it("mock mode still renders mock code", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "true");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<CodePage projectId="PRJ-0421" />);

    expect(await screen.findByText("Mock Code Generator")).toBeInTheDocument();
    expect(await screen.findByText(/PROGRAM Motor_Controller/)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("Run validation calls validate endpoint before navigation", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/projects/PRJ-0421/code")) {
        return Promise.resolve(jsonResponse(artifact("PRJ-0421")));
      }
      if (url.endsWith("/api/projects/PRJ-0421/validate") && init?.method === "POST") {
        return Promise.resolve(jsonResponse(validationReport("PRJ-0421", "CHECKS_PASSED")));
      }
      return Promise.resolve(jsonResponse({ detail: `Unhandled request: ${init?.method ?? "GET"} ${url}` }, 500));
    });
    vi.stubGlobal("fetch", fetchMock);
    const routerPush = (globalThis as unknown as { __nextRouterPush: ReturnType<typeof vi.fn> }).__nextRouterPush;

    render(<CodePage projectId="PRJ-0421" />);
    await screen.findByText("Generated IEC 61131-3 Structured Text");

    fireEvent.click(screen.getByRole("button", { name: /Run validation/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://api.test/api/projects/PRJ-0421/validate",
        expect.objectContaining({ method: "POST" })
      );
      expect(routerPush).toHaveBeenCalledWith("/projects/PRJ-0421/validation");
    });
  });

  it("Run validation failure shows error and does not navigate", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/projects/PRJ-0421/code")) {
        return Promise.resolve(jsonResponse(artifact("PRJ-0421")));
      }
      if (url.endsWith("/api/projects/PRJ-0421/validate") && init?.method === "POST") {
        return Promise.resolve(jsonResponse({ detail: "Validation failed for test." }, 400));
      }
      return Promise.resolve(jsonResponse({ detail: `Unhandled request: ${init?.method ?? "GET"} ${url}` }, 500));
    });
    vi.stubGlobal("fetch", fetchMock);
    const routerPush = (globalThis as unknown as { __nextRouterPush: ReturnType<typeof vi.fn> }).__nextRouterPush;

    render(<CodePage projectId="PRJ-0421" />);
    await screen.findByText("Generated IEC 61131-3 Structured Text");

    fireEvent.click(screen.getByRole("button", { name: /Run validation/i }));

    expect(await screen.findByText(/Validation failed for test\./)).toBeInTheDocument();
    expect(routerPush).not.toHaveBeenCalled();
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

function artifact(projectId: string): CodeArtifact {
  return {
    projectId,
    artifactId: `${projectId}-code-iter-1`,
    language: "structured-text",
    filename: "plc_prj_0421_controller.st",
    source: `PROGRAM PLC_PRJ_0421_Controller
VAR_INPUT
    Start_PB : BOOL;
END_VAR
VAR_OUTPUT
    Motor_Run : BOOL;
END_VAR
VAR
    Run_Cmd : BOOL;
END_VAR
Motor_Run := Run_Cmd;
END_PROGRAM`,
    iteration: 1,
    generatedAt: "2026-05-19T10:00:00Z",
    metrics: {
      loc: 11,
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

function validationReport(projectId: string, status: "CHECKS_PASSED" | "SYNTAX_ERROR" | "FORMAL_VIOLATION"): ValidationReport {
  return {
    projectId,
    artifactId: `${projectId}-code-iter-1`,
    iteration: 1,
    status,
    syntaxPassed: status !== "SYNTAX_ERROR",
    formalPassed: status === "CHECKS_PASSED",
    solver: "static.v1",
    validator: "static.v1",
    evidenceLevel: "STATIC_RULES_PASSED",
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

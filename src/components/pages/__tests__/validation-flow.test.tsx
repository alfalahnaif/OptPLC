import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ValidationPage } from "@/components/pages/validation-page";
import type { ValidationReport } from "@/lib/api-contracts";

describe("Validation frontend flow", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("Validation page renders backend VERIFIED result in real mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    stubFetch(validationReport("PRJ-0421", "VERIFIED"));

    render(<ValidationPage projectId="PRJ-0421" />);

    expect(await screen.findByText("Real Static Validator")).toBeInTheDocument();
    expect((await screen.findAllByText("VERIFIED")).length).toBeGreaterThan(0);
    expect(await screen.findByText("All properties hold")).toBeInTheDocument();
    expect((await screen.findAllByText("static.v1")).length).toBeGreaterThan(0);
    expect(await screen.findByRole("link", { name: /Continue to Optimization/ })).toHaveAttribute("href", "/projects/PRJ-0421/optimization");
  });

  it("Validation page renders backend SYNTAX_ERROR result", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    stubFetch(validationReport("PRJ-0421", "SYNTAX_ERROR", {
      syntaxErrors: ["END_PROGRAM is required for PROGRAM blocks."]
    }));

    render(<ValidationPage projectId="PRJ-0421" />);

    expect(await screen.findByText("SYNTAX_ERROR")).toBeInTheDocument();
    expect(await screen.findByText("Syntax checks failed")).toBeInTheDocument();
    expect(await screen.findByText("END_PROGRAM is required for PROGRAM blocks.")).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /Open Debugging Advice/ })).toHaveAttribute("href", "/projects/PRJ-0421/debugging");
  });

  it("Validation page renders backend FORMAL_VIOLATION result", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    stubFetch(validationReport("PRJ-0421", "FORMAL_VIOLATION", {
      formalErrors: ["Motor_Run is not visibly gated by E_Stop or the safety/fault state."]
    }));

    render(<ValidationPage projectId="PRJ-0421" />);

    expect((await screen.findAllByText("FORMAL_VIOLATION")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Safety checks failed")).toBeInTheDocument();
    expect((await screen.findAllByText("Motor_Run is not visibly gated by E_Stop or the safety/fault state.")).length).toBeGreaterThan(0);
  });

  it("missing CodeArtifact backend error is displayed with guidance", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    stubFetch({ detail: "CodeArtifact must be generated before validation." }, 400);

    render(<ValidationPage projectId="PRJ-0421" />);

    expect(await screen.findByText("Validation report unavailable")).toBeInTheDocument();
    expect(await screen.findByText("Generate Structured Text code before running validation.")).toBeInTheDocument();
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

function validationReport(
  projectId: string,
  status: ValidationReport["status"],
  overrides: Partial<ValidationReport> = {}
): ValidationReport {
  const syntaxPassed = status !== "SYNTAX_ERROR";
  const formalPassed = status === "VERIFIED";
  const failedDetails =
    status === "FORMAL_VIOLATION"
      ? "Motor_Run is not visibly gated by E_Stop or the safety/fault state."
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

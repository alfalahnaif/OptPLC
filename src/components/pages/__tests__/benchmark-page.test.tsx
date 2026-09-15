import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BenchmarkPage } from "@/components/pages/benchmark-page";

describe("Benchmark page benchmark modes", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("loads real benchmark cases from backend", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = stubFetchSequence({ payload: casesPayload() });

    render(<BenchmarkPage />);

    expect(await screen.findByText(/B001 - Motor benchmark case/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/benchmarks/cases",
      expect.objectContaining({ method: "GET" })
    );
  });

  it("runs compare mode and renders comparison table", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = stubFetchSequence({ payload: casesPayload() }, { payload: comparePayload() });

    render(<BenchmarkPage />);
    fireEvent.click(await screen.findByRole("button", { name: /Run Selected/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://api.test/api/benchmarks/compare",
        expect.objectContaining({ method: "POST" })
      );
    });
    expect(await screen.findByText("Lines of Code")).toBeInTheDocument();
    expect((await screen.findAllByText("LLM+RAG")).length).toBeGreaterThan(0);
  });

  it("runs benchmark suite and shows aggregate metrics", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = stubFetchSequence({ payload: casesPayload() }, { payload: suitePayload() });

    render(<BenchmarkPage />);
    fireEvent.click(await screen.findByRole("button", { name: /Run Benchmark Suite/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://api.test/api/benchmarks/run-suite",
        expect.objectContaining({ method: "POST" })
      );
    });
    expect(await screen.findByText("15")).toBeInTheDocument();
    expect(await screen.findByText("llm_rag")).toBeInTheDocument();
  });

  it("mock mode renders without network", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "true");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<BenchmarkPage />);
    expect(await screen.findByText(/B001 - Motor start\/stop with E-stop/)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

function stubFetchSequence(...responses: Array<{ payload: unknown; status?: number }>) {
  const fetchMock = vi.fn().mockImplementation(() => {
    const next = responses.shift() ?? { payload: suitePayload(), status: 200 };
    return Promise.resolve(
      new Response(JSON.stringify(next.payload), {
        status: next.status ?? 200,
        headers: { "Content-Type": "application/json" }
      })
    );
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function casesPayload() {
  return [
    {
      id: "B001",
      name: "Motor benchmark case",
      domain: "Motor Control",
      complexity: "simple",
      requirement: "Requirement text",
      safetyConstraints: ["Constraint"],
      expectedInputs: ["Start_PB"],
      expectedOutputs: ["Motor_Run"],
      expectedProperties: [{ id: "P1", description: "summary" }]
    }
  ];
}

function comparePayload() {
  return {
    caseId: "B001",
    results: {
      rule_based: mockResult("rule_based"),
      llm: mockResult("llm"),
      llm_rag: mockResult("llm_rag")
    },
    comparison: {
      llmVsBaseline: { locDelta: -23, ccDelta: -6, miDelta: 26, scanDelta: 8080, repairIterations: 2, verified: true },
      ragVsLlm: { locDelta: -4, ccDelta: -1, miDelta: 3, scanDelta: 900, repairIterations: 1, verified: true },
      ragVsBaseline: { locDelta: -27, ccDelta: -7, miDelta: 29, scanDelta: 8980, repairIterations: 1, verified: true }
    }
  };
}

function suitePayload() {
  return {
    runId: "suite-1",
    completedAt: "2026-05-21T06:00:10Z",
    totalCases: 5,
    totalRuns: 15,
    cases: [comparePayload()],
    summary: {
      totalRuns: 15,
      byMode: {
        rule_based: { avgLoc: 85, avgCC: 14, verificationRate: 100, avgRepairIterations: 0 },
        llm: { avgLoc: 62, avgCC: 8, verificationRate: 100, avgRepairIterations: 2 },
        llm_rag: { avgLoc: 58, avgCC: 7, verificationRate: 100, avgRepairIterations: 1 }
      },
      bestMode: "llm_rag",
      cases: []
    }
  };
}

function mockResult(mode: "rule_based" | "llm" | "llm_rag") {
  if (mode === "rule_based") {
    return {
      caseId: "B001",
      mode,
      domain: "Motor Control",
      verified: true,
      validationStatus: "CHECKS_PASSED",
      repairIterations: 0,
      generationTimeMs: 120,
      metrics: { loc: 85, cyclomaticComplexity: 14, maintainabilityIndex: 42, estimatedScanTimeMs: 120 },
      ragSourcesUsed: [],
      llmProvider: null,
      llmModel: null,
      generatedCode: "PROGRAM A\nEND_PROGRAM",
      error: null
    };
  }
  if (mode === "llm") {
    return {
      caseId: "B001",
      mode,
      domain: "Motor Control",
      verified: true,
      validationStatus: "CHECKS_PASSED",
      repairIterations: 2,
      generationTimeMs: 8200,
      metrics: { loc: 62, cyclomaticComplexity: 8, maintainabilityIndex: 68, estimatedScanTimeMs: 8200 },
      ragSourcesUsed: [],
      llmProvider: "anthropic",
      llmModel: "model",
      generatedCode: "PROGRAM B\nEND_PROGRAM",
      error: null
    };
  }
  return {
    caseId: "B001",
    mode,
    domain: "Motor Control",
    verified: true,
    validationStatus: "CHECKS_PASSED",
    repairIterations: 1,
    generationTimeMs: 9100,
    metrics: { loc: 58, cyclomaticComplexity: 7, maintainabilityIndex: 71, estimatedScanTimeMs: 9100 },
    ragSourcesUsed: ["source"],
    llmProvider: "anthropic",
    llmModel: "model",
    generatedCode: "PROGRAM C\nEND_PROGRAM",
    error: null
  };
}

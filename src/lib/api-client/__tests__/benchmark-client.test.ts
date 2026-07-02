import { afterEach, describe, expect, it, vi } from "vitest";

import { getBenchmarkCases, runBenchmarkCase, runBenchmarkSuite } from "@/lib/api-client";

describe("benchmark API client transport", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("calls GET /api/benchmarks/cases in real mode", async () => {
    const fetchMock = stubRealApi([
      {
        id: "B001",
        name: "Motor benchmark",
        domain: "Motor Control",
        complexity: "medium",
        requirement: "Benchmark requirement",
        safetyConstraints: ["No auto restart"],
        expectedInputs: ["Start_PB"],
        expectedOutputs: ["Motor_Run"],
        expectedProperties: [{ id: "P1", description: "summary" }]
      }
    ]);

    await expect(getBenchmarkCases()).resolves.toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/benchmarks/cases",
      expect.objectContaining({ method: "GET" })
    );
  });

  it("calls POST /api/benchmarks/run in real mode", async () => {
    const fetchMock = stubRealApi({
      caseId: "B001",
      mode: "llm",
      domain: "Motor Control",
      verified: true,
      validationStatus: "VERIFIED",
      repairIterations: 1,
      generationTimeMs: 8200,
      metrics: {
        loc: 62,
        cyclomaticComplexity: 8,
        maintainabilityIndex: 68,
        estimatedScanTimeMs: 220
      },
      ragSourcesUsed: [],
      llmProvider: "anthropic",
      llmModel: "claude-sonnet-4-20250514",
      generatedCode: "PROGRAM Test\nEND_PROGRAM",
      error: null
    });

    await expect(runBenchmarkCase("B001", "llm")).resolves.toMatchObject({ caseId: "B001" });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/benchmarks/run",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("calls POST /api/benchmarks/run-suite in real mode", async () => {
    const fetchMock = stubRealApi({
      runId: "suite-1",
      completedAt: "2026-05-21T06:00:30Z",
      totalCases: 5,
      totalRuns: 15,
      cases: [],
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
    });
    await expect(runBenchmarkSuite()).resolves.toMatchObject({ totalRuns: 15 });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/benchmarks/run-suite",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("uses mock fallback in mock mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "true");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await expect(getBenchmarkCases()).resolves.toHaveLength(5);
    await expect(runBenchmarkSuite()).resolves.toMatchObject({ totalRuns: 15 });
    expect(fetchMock).not.toHaveBeenCalled();
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

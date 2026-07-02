import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OptimizationPage } from "@/components/pages/optimization-page";
import { MetricsPage } from "@/components/pages/metrics-page";
import { CodePage } from "@/components/pages/code-page";
import type { CodeArtifact, OptimizationReport, OptimizationStatus, StructuredTextMetrics, ValidationStatus } from "@/lib/api-contracts";
import { optimizeCode } from "@/lib/api-client";

describe("Optimization frontend flow", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("optimizeCode client calls correct backend endpoint in real mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = stubFetch(optimizationReport("PRJ-0421", "OPTIMIZED"));

    await optimizeCode("PRJ-0421");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/projects/PRJ-0421/optimize",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("Optimization page renders OPTIMIZED report", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    stubFetch(optimizationReport("PRJ-0421", "OPTIMIZED"));

    render(<OptimizationPage projectId="PRJ-0421" />);

    expect(await screen.findByText("Real Backend OptimizationReport")).toBeInTheDocument();
    expect((await screen.findAllByText("OPTIMIZED")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Structural Simplification")).toBeInTheDocument();
    expect(await screen.findByText("Logic Compaction")).toBeInTheDocument();
    expect(await screen.findByText("Maintainability Enhancement")).toBeInTheDocument();
  });

  it("Optimization page renders NO_CHANGES", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    stubFetch(optimizationReport("PRJ-0421", "NO_CHANGES", { changed: false }));

    render(<OptimizationPage projectId="PRJ-0421" />);

    expect((await screen.findAllByText("NO_CHANGES")).length).toBeGreaterThan(0);
    expect(await screen.findByText("no changes needed")).toBeInTheDocument();
  });

  it("Optimization page renders ROLLED_BACK", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    stubFetch(optimizationReport("PRJ-0421", "ROLLED_BACK", { rollback: true }));

    render(<OptimizationPage projectId="PRJ-0421" />);

    expect((await screen.findAllByText("ROLLED_BACK")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Rollback events")).toBeInTheDocument();
    expect(await screen.findByText("Candidate failed static revalidation and was rolled back.")).toBeInTheDocument();
  });

  it("Optimization page renders CANNOT_OPTIMIZE", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    stubFetch(optimizationReport("PRJ-0421", "CANNOT_OPTIMIZE", { revalidationStatus: "FORMAL_VIOLATION" }));

    render(<OptimizationPage projectId="PRJ-0421" />);

    expect((await screen.findAllByText("CANNOT_OPTIMIZE")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Revalidation FORMAL_VIOLATION")).toBeInTheDocument();
  });

  it("Optimization page shows empty guidance when report is missing", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    stubFetch({ detail: "Optimization report for project PRJ-0421 was not found." }, 404);

    render(<OptimizationPage projectId="PRJ-0421" />);

    expect(await screen.findByText("No optimization results")).toBeInTheDocument();
    expect(await screen.findByText("Run optimization before viewing results.")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Run Optimization Now" })).toBeInTheDocument();
  });

  it("Run Optimization Now creates and renders persisted report", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    let optimized = false;
    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/optimization")) {
        if (!optimized) {
          return Promise.resolve(new Response(JSON.stringify({ detail: "Optimization report for project PRJ-0421 was not found." }), { status: 404, headers: { "Content-Type": "application/json" } }));
        }
        return Promise.resolve(new Response(JSON.stringify(optimizationReport("PRJ-0421", "OPTIMIZED")), { status: 200, headers: { "Content-Type": "application/json" } }));
      }
      if (url.endsWith("/optimize") && init?.method === "POST") {
        optimized = true;
        return Promise.resolve(new Response(JSON.stringify(optimizationReport("PRJ-0421", "OPTIMIZED")), { status: 200, headers: { "Content-Type": "application/json" } }));
      }
      return Promise.resolve(new Response(JSON.stringify({ detail: "Unhandled request" }), { status: 500, headers: { "Content-Type": "application/json" } }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<OptimizationPage projectId="PRJ-0421" />);
    fireEvent.click(await screen.findByRole("button", { name: "Run Optimization Now" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://api.test/api/projects/PRJ-0421/optimize",
        expect.objectContaining({ method: "POST" })
      );
    });
    expect(await screen.findByText("Structural Simplification")).toBeInTheDocument();
  });

  it("before and after metrics plus rollback events render correctly", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    stubFetch(optimizationReport("PRJ-0421", "OPTIMIZED", { rollback: true }));

    render(<OptimizationPage projectId="PRJ-0421" />);

    expect(await screen.findByText("Before / after metrics")).toBeInTheDocument();
    expect(await screen.findByText("4.1 ms")).toBeInTheDocument();
    expect(await screen.findByText("2.4 ms")).toBeInTheDocument();
    expect(await screen.findByText("-1.7 ms")).toBeInTheDocument();
    expect(await screen.findByText("Candidate failed static revalidation and was rolled back.")).toBeInTheDocument();
  });

  it("mock mode still renders mock optimization result", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "true");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<OptimizationPage projectId="PRJ-0421" />);

    expect(await screen.findByText("Mock Optimizer")).toBeInTheDocument();
    expect(await screen.findByText(/Static optimizer applied 3 pass/)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("Code page renders latest persisted code artifact in real mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const optimized = optimizationReport("PRJ-OPT-CODE", "OPTIMIZED");
    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/optimization")) return Promise.resolve(new Response(JSON.stringify(optimized), { status: 200, headers: { "Content-Type": "application/json" } }));
      if (url.endsWith("/code")) return Promise.resolve(new Response(JSON.stringify(optimized.optimizedCode), { status: 200, headers: { "Content-Type": "application/json" } }));
      return Promise.resolve(new Response(JSON.stringify({}), { status: 404, headers: { "Content-Type": "application/json" } }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<OptimizationPage projectId="PRJ-OPT-CODE" />);
    expect(await screen.findByText("Real Backend OptimizationReport")).toBeInTheDocument();

    render(<CodePage projectId="PRJ-OPT-CODE" />);

    expect(await screen.findByText("Real Backend CodeArtifact")).toBeInTheDocument();
    expect((await screen.findAllByText("motor_controller_optimized.st")).length).toBeGreaterThan(0);
    expect((await screen.findAllByText("static_optimizer.v1")).length).toBeGreaterThan(0);
  });

  it("Metrics page shows real backend metrics badge in real mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const report = {
      projectId: "PRJ-0421",
      source: { selected: "generated_code", generatedCode: "PRJ-0421-code-iter-1" },
      beforeMetrics: { loc: 30, cyclomaticComplexity: 6, maintainabilityIndex: 70, estimatedScanTimeMs: 3.2 },
      afterMetrics: { loc: 28, cyclomaticComplexity: 5, maintainabilityIndex: 74, estimatedScanTimeMs: 2.9 },
      metricsDelta: {
        locDelta: -2,
        cyclomaticComplexityDelta: -1,
        maintainabilityIndexDelta: 4,
        estimatedScanTimeDelta: -0.3,
        locReductionPercent: 6.7,
        complexityReductionPercent: 16.7,
        maintainabilityImprovementPercent: 5.7,
        scanTimeReductionPercent: 9.4
      },
      history: [],
      latestValidationStatus: "VERIFIED",
      latestOptimizationStatus: "OPTIMIZED",
      createdAt: "2026-05-19T10:00:00Z",
      summary: "Metrics report."
    };
    stubFetch(report);

    render(<MetricsPage projectId="PRJ-0421" />);
    expect(await screen.findByText("Real Backend MetricsReport")).toBeInTheDocument();
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

function optimizationReport(
  projectId: string,
  status: OptimizationStatus,
  options: { changed?: boolean; rollback?: boolean; revalidationStatus?: ValidationStatus } = {}
): OptimizationReport {
  const changed = options.changed ?? status === "OPTIMIZED";
  const revalidationStatus = options.revalidationStatus ?? "VERIFIED";
  const beforeMetrics: StructuredTextMetrics = {
    loc: 47,
    cyclomaticComplexity: 9,
    maintainabilityIndex: 68,
    estimatedScanTimeMs: 4.1
  };
  const afterMetrics: StructuredTextMetrics = changed
    ? {
        loc: 33,
        cyclomaticComplexity: 4,
        maintainabilityIndex: 89,
        estimatedScanTimeMs: 2.4
      }
    : beforeMetrics;
  const originalCode = artifact(projectId, `${projectId}-code-iter-2`, "motor_controller.st", "template_based.repair.v1", 2, beforeMetrics, "PROGRAM Motor_Controller\nEND_PROGRAM");
  const optimizedCode = artifact(projectId, `${projectId}-code-optimized-3`, "motor_controller_optimized.st", "static_optimizer.v1", 3, afterMetrics, "PROGRAM Motor_Controller\n(* optimized *)\nEND_PROGRAM");
  const rollbackEvents = options.rollback
    ? [
        {
          passName: "Logic Compaction",
          reason: "Candidate failed static revalidation and was rolled back.",
          revalidationStatus: "FORMAL_VIOLATION" as const
        }
      ]
    : [];

  return {
    projectId,
    sourceArtifactId: originalCode.artifactId,
    optimizedArtifactId: optimizedCode.artifactId,
    status,
    optimizer: "static.v1",
    originalCode,
    optimizedCode,
    passes: [
      {
        name: "Structural Simplification",
        status: changed ? "applied" : "no_changes",
        summary: changed ? "Collapsed compatible nested safety IF blocks." : "no changes needed",
        accepted: true,
        revalidationStatus,
        beforeMetrics,
        afterMetrics
      },
      {
        name: "Logic Compaction",
        status: options.rollback ? "rolled_back" : changed ? "applied" : "no_changes",
        summary: options.rollback ? "Unsafe compaction rolled back." : "Compacted repeated assignments.",
        accepted: !options.rollback,
        revalidationStatus: options.rollback ? "FORMAL_VIOLATION" : revalidationStatus,
        beforeMetrics,
        afterMetrics
      },
      {
        name: "Maintainability Enhancement",
        status: changed ? "applied" : "no_changes",
        summary: "Added deterministic maintainability annotations.",
        accepted: true,
        revalidationStatus,
        beforeMetrics,
        afterMetrics
      }
    ],
    beforeMetrics,
    afterMetrics,
    metricsDelta: {
      loc: afterMetrics.loc - beforeMetrics.loc,
      cyclomaticComplexity: afterMetrics.cyclomaticComplexity - beforeMetrics.cyclomaticComplexity,
      maintainabilityIndex: afterMetrics.maintainabilityIndex - beforeMetrics.maintainabilityIndex,
      estimatedScanTimeMs: Number((afterMetrics.estimatedScanTimeMs - beforeMetrics.estimatedScanTimeMs).toFixed(1)),
      locReductionPercent: changed ? 29.8 : 0,
      cyclomaticReductionPercent: changed ? 55.6 : 0,
      maintainabilityGainPercent: changed ? 30.9 : 0,
      scanTimeReductionPercent: changed ? 41.5 : 0
    },
    revalidationStatus,
    rollbackEvents,
    createdAt: "2026-05-19T10:00:00Z",
    summary:
      status === "NO_CHANGES"
        ? "Static optimizer found no safe source changes; verified code was preserved."
        : "Static optimizer applied 3 pass(es); every accepted pass revalidated successfully.",
    revalidated: revalidationStatus === "VERIFIED"
  };
}

function artifact(
  projectId: string,
  artifactId: string,
  filename: string,
  generator: string,
  iteration: number,
  metrics: StructuredTextMetrics,
  source: string
): CodeArtifact {
  return {
    projectId,
    artifactId,
    filename,
    language: "structured-text",
    source,
    iteration,
    generatedAt: "2026-05-19T10:00:00Z",
    metrics: {
      loc: metrics.loc,
      cyclomaticComplexity: metrics.cyclomaticComplexity,
      maintainabilityIndex: metrics.maintainabilityIndex
    },
    metadata: {
      generator,
      iecStandard: "IEC 61131-3",
      sourcePlanId: projectId,
      createdAt: "2026-05-19T10:00:00Z",
      iteration
    }
  };
}

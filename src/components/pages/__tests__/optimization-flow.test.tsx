import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OptimizationPage } from "@/components/pages/optimization-page";
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

    expect(await screen.findByText("Real Static Optimizer")).toBeInTheDocument();
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

  it("Code page shows optimized code tab after optimization report is cached", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    stubFetch(optimizationReport("PRJ-OPT-CODE", "OPTIMIZED"));

    render(<OptimizationPage projectId="PRJ-OPT-CODE" />);
    expect(await screen.findByText("Real Static Optimizer")).toBeInTheDocument();

    render(<CodePage projectId="PRJ-OPT-CODE" />);

    expect(await screen.findByRole("tab", { name: "Optimized" })).toBeInTheDocument();
    expect((await screen.findAllByText("motor_controller_optimized.st")).length).toBeGreaterThan(0);
    expect((await screen.findAllByText("static_optimizer.v1")).length).toBeGreaterThan(0);
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

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { FinalReport } from "@/lib/api-contracts";
import { ReportPage } from "@/components/pages/report-page";

const useApiResourceMock = vi.fn();
const exportReportJsonMock = vi.fn();
const exportReportMarkdownMock = vi.fn();

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return {
    ...actual,
    ACTIVE_PROJECT_ID: "PRJ-0421",
    exportReportJson: (...args: unknown[]) => exportReportJsonMock(...args),
    exportReportMarkdown: (...args: unknown[]) => exportReportMarkdownMock(...args),
    getFinalReport: vi.fn(),
    useApiResource: (...args: unknown[]) => useApiResourceMock(...args)
  };
});

describe("ReportPage", () => {
  beforeEach(() => {
    useApiResourceMock.mockReset();
    exportReportJsonMock.mockReset();
    exportReportMarkdownMock.mockReset();
    exportReportJsonMock.mockResolvedValue(new Blob(["{}"], { type: "application/json" }));
    exportReportMarkdownMock.mockResolvedValue(new Blob(["# report"], { type: "text/markdown" }));
    Object.defineProperty(URL, "createObjectURL", {
      writable: true,
      value: vi.fn(() => "blob:mock")
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      writable: true,
      value: vi.fn()
    });
  });

  it("renders real report data", async () => {
    useApiResourceMock.mockReturnValue({
      state: "ready",
      data: reportFixture(),
      error: null
    });

    render(<ReportPage projectId="PRJ-0421" />);

    expect(await screen.findByText("Project summary")).toBeInTheDocument();
    expect(await screen.findByText("Conveyor Controller")).toBeInTheDocument();
    expect(await screen.findByText("Validation passed.")).toBeInTheDocument();
  });

  it("renders missing section placeholders", async () => {
    useApiResourceMock.mockReturnValue({
      state: "ready",
      data: reportFixture({
        requirement: null,
        planObject: null,
        codeArtifact: null,
        metrics: null
      }),
      error: null
    });

    render(<ReportPage projectId="PRJ-0421" />);

    expect(await screen.findAllByText("Not generated yet")).not.toHaveLength(0);
  });

  it("renders backend error state", async () => {
    useApiResourceMock.mockReturnValue({
      state: "error",
      data: null,
      error: new Error("API request failed (400): no project artifacts exist yet")
    });

    render(<ReportPage projectId="PRJ-0421" />);
    expect(await screen.findByText("Final report unavailable")).toBeInTheDocument();
    expect(await screen.findByText(/no project artifacts exist yet/)).toBeInTheDocument();
  });

  it("export JSON button calls report client", async () => {
    useApiResourceMock.mockReturnValue({
      state: "ready",
      data: reportFixture(),
      error: null
    });

    render(<ReportPage projectId="PRJ-0421" />);
    fireEvent.click(await screen.findByRole("button", { name: "Export JSON" }));

    await waitFor(() => {
      expect(exportReportJsonMock).toHaveBeenCalledWith("PRJ-0421");
    });
  });

  it("export Markdown button calls report client", async () => {
    useApiResourceMock.mockReturnValue({
      state: "ready",
      data: reportFixture(),
      error: null
    });

    render(<ReportPage projectId="PRJ-0421" />);
    fireEvent.click(await screen.findByRole("button", { name: "Export Markdown" }));

    await waitFor(() => {
      expect(exportReportMarkdownMock).toHaveBeenCalledWith("PRJ-0421");
    });
  });

  it("PDF button is disabled and marked coming soon", async () => {
    useApiResourceMock.mockReturnValue({
      state: "ready",
      data: reportFixture(),
      error: null
    });

    render(<ReportPage projectId="PRJ-0421" />);
    const pdfButton = await screen.findByRole("button", { name: "Export PDF (Coming soon)" });
    expect(pdfButton).toBeDisabled();
  });

  it("export failure displays error message", async () => {
    useApiResourceMock.mockReturnValue({
      state: "ready",
      data: reportFixture(),
      error: null
    });
    exportReportJsonMock.mockRejectedValue(new Error("Export failed due to backend error."));

    render(<ReportPage projectId="PRJ-0421" />);
    fireEvent.click(await screen.findByRole("button", { name: "Export JSON" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Export failed due to backend error.");
  });
});

function reportFixture(overrides: Partial<FinalReport> = {}): FinalReport {
  return {
    projectId: "PRJ-0421",
    reportId: "PRJ-0421-final-report",
    generatedAt: "2026-05-20T18:00:00Z",
    summary: "Final report generated from persisted artifacts.",
    validation: {
      projectId: "PRJ-0421",
      artifactId: "PRJ-0421-code-iter-1",
      iteration: 1,
      status: "VERIFIED",
      syntaxPassed: true,
      formalPassed: true,
      solver: "static.v1",
      validator: "static.v1",
      checkedAt: "2026-05-20T18:00:00Z",
      summary: "Validation passed.",
      syntaxErrors: [],
      formalErrors: [],
      safetyResults: [],
      properties: [],
      errors: [],
      counterexamples: []
    },
    optimization: null,
    metrics: {
      projectId: "PRJ-0421",
      source: { selected: "generated_code", generatedCode: "PRJ-0421-code-iter-1" },
      beforeMetrics: { loc: 10, cyclomaticComplexity: 3, maintainabilityIndex: 80, estimatedScanTimeMs: 2 },
      afterMetrics: { loc: 8, cyclomaticComplexity: 2, maintainabilityIndex: 85, estimatedScanTimeMs: 1.5 },
      metricsDelta: {
        locDelta: -2,
        cyclomaticComplexityDelta: -1,
        maintainabilityIndexDelta: 5,
        estimatedScanTimeDelta: -0.5,
        locReductionPercent: 20,
        complexityReductionPercent: 33.3,
        maintainabilityImprovementPercent: 6.25,
        scanTimeReductionPercent: 25
      },
      history: [],
      latestValidationStatus: "VERIFIED",
      latestOptimizationStatus: null,
      createdAt: "2026-05-20T18:00:00Z",
      summary: "Metrics generated."
    },
    project: {
      id: "PRJ-0421",
      name: "Conveyor Controller",
      domain: "Motor Control",
      description: "Conveyor motor safety logic",
      standard: "IEC 61131-3",
      targetLanguage: "Structured Text",
      status: "planned",
      createdAt: "2026-05-20T17:00:00Z",
      updatedAt: "2026-05-20T18:00:00Z"
    },
    requirement: {
      projectId: "PRJ-0421",
      text: "Control conveyor motor safely.",
      safetyConstraints: ["No auto restart."],
      performanceTargets: {
        maxScanTimeMs: 5,
        maxCyclomaticComplexity: 8,
        minMaintainabilityIndex: 75,
        maxIterations: 5
      }
    },
    planObject: {
      projectId: "PRJ-0421",
      agent: "PlanningAgent/rule_based.v1",
      generatedAt: "2026-05-20T17:30:00Z",
      inputs: [{ name: "Start", type: "BOOL", description: "Start button" }],
      outputs: [{ name: "Run", type: "BOOL", description: "Motor run output" }],
      logicRules: ["Latch run command."],
      safetyConstraints: ["No auto restart."],
      scope: {
        standard: "IEC 61131-3",
        edition: "3rd ed. (2013)",
        language: "Structured Text",
        runtime: "CODESYS / TwinCAT compatible"
      }
    },
    codeArtifact: {
      projectId: "PRJ-0421",
      artifactId: "PRJ-0421-code-iter-1",
      language: "structured-text",
      filename: "controller.st",
      source: "PROGRAM PLC\nEND_PROGRAM",
      iteration: 1,
      generatedAt: "2026-05-20T17:40:00Z",
      metrics: { loc: 2, cyclomaticComplexity: 1, maintainabilityIndex: 90 },
      metadata: {
        generator: "template_based.v1",
        iecStandard: "IEC 61131-3",
        sourcePlanId: "PRJ-0421",
        createdAt: "2026-05-20T17:40:00Z",
        iteration: 1
      }
    },
    debugging: null,
    repairLoop: null,
    validationSummary: "Validation passed.",
    debuggingSummary: "Debugging has not been run yet.",
    repairLoopSummary: "Repair loop has not been run yet.",
    optimizationSummary: "Optimization has not been run yet.",
    metricsSummary: "Metrics generated.",
    finalStatusSummary: "Project status is 'planned'.",
    recommendations: ["Run optimization for additional improvements."],
    limitationsDisclaimer: "PDF export remains future work.",
    ...overrides
  };
}

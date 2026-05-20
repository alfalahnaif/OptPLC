import { afterEach, describe, expect, it, vi } from "vitest";

import type { FinalReport } from "@/lib/api-contracts";
import { exportReportJson, exportReportMarkdown, getFinalReport } from "@/lib/api-client";

describe("report API client", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("calls GET /api/projects/{id}/report when mock mode is disabled", async () => {
    const payload = reportResponse("PRJ-0421");
    const fetchMock = stubRealApi(payload);

    await expect(getFinalReport("PRJ-0421")).resolves.toEqual(payload);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/projects/PRJ-0421/report",
      expect.objectContaining({ method: "GET" })
    );
  });

  it("returns mock report in mock mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "true");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await expect(getFinalReport("PRJ-0421")).resolves.toMatchObject({
      projectId: "PRJ-0421",
      reportId: "PRJ-0421-final-report"
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("calls JSON export endpoint in real mode", async () => {
    const fetchMock = stubRealApi('{"projectId":"PRJ-0421"}', 200, "application/json");

    const blob = await exportReportJson("PRJ-0421");
    expect(await blob.text()).toContain('"projectId":"PRJ-0421"');
    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/projects/PRJ-0421/report/export/json",
      expect.objectContaining({ method: "GET" })
    );
  });

  it("calls Markdown export endpoint in real mode", async () => {
    const fetchMock = stubRealApi("# PLCForge Final Report", 200, "text/markdown");

    const blob = await exportReportMarkdown("PRJ-0421");
    expect(await blob.text()).toContain("# PLCForge Final Report");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/projects/PRJ-0421/report/export/markdown",
      expect.objectContaining({ method: "GET" })
    );
  });
});

function stubRealApi(payload: unknown, status = 200, contentType = "application/json") {
  vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(typeof payload === "string" ? payload : JSON.stringify(payload), {
      status,
      headers: {
        "Content-Type": contentType
      }
    })
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function reportResponse(projectId: string): FinalReport {
  return {
    projectId,
    reportId: `${projectId}-final-report`,
    generatedAt: "2026-05-20T18:00:00Z",
    summary: "Final report generated from persisted artifacts.",
    validation: null,
    optimization: null,
    metrics: null,
    project: {
      id: projectId,
      name: "Conveyor Controller",
      domain: "Motor Control",
      description: "Conveyor motor safety logic",
      standard: "IEC 61131-3",
      targetLanguage: "Structured Text",
      status: "planned",
      createdAt: "2026-05-20T17:00:00Z",
      updatedAt: "2026-05-20T18:00:00Z"
    },
    requirement: null,
    planObject: null,
    codeArtifact: null,
    debugging: null,
    repairLoop: null,
    validationSummary: "Validation has not been run yet.",
    debuggingSummary: "Debugging has not been run yet.",
    repairLoopSummary: "Repair loop has not been run yet.",
    optimizationSummary: "Optimization has not been run yet.",
    metricsSummary: "Metrics have not been generated yet.",
    finalStatusSummary: "Project status is 'planned'.",
    recommendations: ["Run validation to generate syntax and safety evidence."],
    limitationsDisclaimer: "PDF export remains future work."
  };
}

import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RequirementsPage } from "@/components/pages/requirements-page";
import type { RequirementPayload } from "@/lib/api-contracts";

describe("Requirements requirement-driven preview", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("shows empty-state guidance and hides inferred preview before analysis", async () => {
    renderRealModePage({
      projectId: "PRJ-BATCH-EMPTY",
      domain: "Sequential Batch",
      requirementText: ""
    });

    expect(
      await screen.findByText("Enter a control requirement and analyze it to preview suggested I/O, logic, and safety constraints.")
    ).toBeInTheDocument();
    expect(screen.queryByText("Inferred inputs -")).not.toBeInTheDocument();
    expect(screen.queryByText("Confirmed outputs -")).not.toBeInTheDocument();
    expect(screen.queryByText("Suggested outputs (not yet confirmed)")).not.toBeInTheDocument();
    expect(screen.queryByText("Suggested internals -")).not.toBeInTheDocument();
    expect(screen.queryByText("Suggested constraints")).not.toBeInTheDocument();
  });

  it("shows validation when Analyze Requirement is clicked with empty text", async () => {
    renderRealModePage({
      projectId: "PRJ-ANALYZE-EMPTY",
      domain: "Sequential Batch",
      requirementText: ""
    });

    fireEvent.click(await screen.findByRole("button", { name: "Analyze Requirement" }));
    expect(await screen.findByText("Enter a control requirement first.")).toBeInTheDocument();
  });

  it("detects Sequential Batch suggestions only after analysis", async () => {
    renderRealModePage({
      projectId: "PRJ-BATCH-1",
      domain: "Sequential Batch",
      requirementText: ""
    });

    const textarea = await screen.findByLabelText("Requirement text");
    fireEvent.change(textarea, {
      target: { value: "Operator start batch, fill complete at high level, mix timer done, then open fill valve and drain valve." }
    });
    fireEvent.click(screen.getByRole("button", { name: "Analyze Requirement" }));

    expect(await screen.findByText("Sequential Batch")).toBeInTheDocument();
    expect(await screen.findByText("Fill_Valve : BOOL")).toBeInTheDocument();
    expect(await screen.findByText("Drain_Valve : BOOL")).toBeInTheDocument();
    expect(await screen.findByText(/Inferred inputs -/)).toBeInTheDocument();
    expect(await screen.findByText(/Step_State/)).toBeInTheDocument();
    expect(await screen.findByText(/Fault_State/)).toBeInTheDocument();
  });

  it("live preview safety count matches confirmed list count", async () => {
    renderRealModePage({
      projectId: "PRJ-SAFETY-COUNT",
      domain: "Sequential Batch",
      requirementText: "Sequential batch process"
    });

    const addInput = await screen.findByPlaceholderText("Add a safety property");
    fireEvent.change(addInput, { target: { value: "Constraint 1" } });
    fireEvent.click(screen.getByRole("button", { name: /Add/ }));
    fireEvent.change(addInput, { target: { value: "Constraint 2" } });
    fireEvent.click(screen.getByRole("button", { name: /Add/ }));

    expect(await screen.findByText("Safety constraints - 3")).toBeInTheDocument();
  });
});

function renderRealModePage({
  projectId,
  domain,
  requirementText
}: {
  projectId: string;
  domain: string;
  requirementText: string;
}) {
  vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");

  const persisted = persistedRequirement(projectId, domain, requirementText);
  const project = persistedProject(projectId, domain);
  const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input.toString();
    if (url.endsWith(`/api/projects/${projectId}/requirements`)) {
      return Promise.resolve(jsonResponse(persisted));
    }
    if (url.endsWith(`/api/projects/${projectId}`)) {
      return Promise.resolve(jsonResponse(project));
    }
    return Promise.resolve(jsonResponse({ detail: "Not found" }, 404));
  });
  vi.stubGlobal("fetch", fetchMock);

  render(<RequirementsPage projectId={projectId} />);
}

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json"
    }
  });
}

function persistedRequirement(projectId: string, domain: string, text: string): RequirementPayload {
  return {
    projectId,
    text,
    safetyConstraints: ["Constraint A"],
    confirmedOutputs: [],
    performanceTargets: {
      maxScanTimeMs: 9,
      maxCyclomaticComplexity: 11,
      minMaintainabilityIndex: 72,
      maxIterations: 6
    },
    domain,
    complexityTier: "medium",
    submittedAt: "2026-05-21T08:30:00Z",
    updatedAt: "2026-05-21T08:30:00Z"
  };
}

function persistedProject(projectId: string, domain: string) {
  return {
    id: projectId,
    name: `${domain} Project`,
    description: `${domain} flow`,
    domain,
    standard: "IEC 61131-3",
    targetLanguage: "Structured Text",
    status: "draft",
    createdAt: "2026-05-21T08:30:00Z",
    updatedAt: "2026-05-21T08:30:00Z"
  };
}

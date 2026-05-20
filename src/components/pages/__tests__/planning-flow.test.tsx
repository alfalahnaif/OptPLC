import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi, type Mock } from "vitest";

import type { PlanObject, Project, WorkflowEvent } from "@/lib/api-contracts";
import { NewProjectPage } from "@/components/pages/new-project-page";
import { PlanPage } from "@/components/pages/plan-page";
import { RequirementsPage } from "@/components/pages/requirements-page";

describe("Planning Agent frontend flow", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    routerPush().mockClear();
  });

  it("new project creates a backend project and navigates to project requirements in real mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = stubFetch(projectResponse("PRJ-0500"), 201);

    render(<NewProjectPage />);
    fireEvent.click(screen.getByRole("button", { name: /Continue to Requirements/ }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://api.test/api/projects",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining('"complexityTier":"medium"')
        })
      );
    });
    await waitFor(() => expect(routerPush()).toHaveBeenCalledWith("/projects/PRJ-0500/requirements"));
  });

  it("requirement submit calls submitRequirements and navigates in real mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = stubFetch(workflowEvent("PRJ-0421"));

    render(<RequirementsPage projectId="PRJ-0421" />);
    await screen.findByDisplayValue(/Control a three-phase motor/);
    fireEvent.click(screen.getByRole("button", { name: /Generate Plan Object/ }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://api.test/api/projects/PRJ-0421/requirements",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining('"projectId":"PRJ-0421"')
        })
      );
    });
    await waitFor(() => expect(routerPush()).toHaveBeenCalledWith("/projects/PRJ-0421/plan"));
  });

  it("backend validation error is displayed for blank requirement", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    stubFetch({ detail: "Requirement text must not be empty." }, 400);

    render(<RequirementsPage projectId="PRJ-0421" />);
    const textarea = await screen.findByDisplayValue(/Control a three-phase motor/);
    fireEvent.change(textarea, { target: { value: "   " } });
    fireEvent.click(screen.getByRole("button", { name: /Generate Plan Object/ }));

    expect(await screen.findByText("Requirement submission failed")).toBeInTheDocument();
    expect(await screen.findByText(/Requirement text must not be empty/)).toBeInTheDocument();
    expect(routerPush()).not.toHaveBeenCalled();
  });

  it("plan page calls generatePlan endpoint in real mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = stubFetch(backendPlan("PRJ-0421"));

    render(<PlanPage projectId="PRJ-0421" />);

    expect(await screen.findByText("Real Backend Planning Agent")).toBeInTheDocument();
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://api.test/api/projects/PRJ-0421/plan",
        expect.objectContaining({ method: "POST" })
      );
    });
  });

  it("mock mode still renders the mock plan without backend fetch", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "true");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<PlanPage projectId="PRJ-0421" />);

    expect(await screen.findByText("Mock Planning Mode")).toBeInTheDocument();
    expect(await screen.findByText(/"agent": "PlanningAgent\/v1.4"/)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("real mode renders backend PlanObject", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    stubFetch(backendPlan("PRJ-0777"));

    render(<PlanPage projectId="PRJ-0777" />);

    expect(await screen.findByText("Vehicle_Detect")).toBeInTheDocument();
    expect(await screen.findByText("Ped_Walk")).toBeInTheDocument();
    expect(await screen.findByText(/"agent": "PlanningAgent\/rule_based.v1"/)).toBeInTheDocument();
  });
});

function routerPush() {
  return (globalThis as unknown as { __nextRouterPush: Mock }).__nextRouterPush;
}

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

function projectResponse(id: string): Project {
  return {
    id,
    name: "Motor Control - Conveyor M-12",
    domain: "Motor Control",
    description: "Motor control project.",
    standard: "IEC 61131-3",
    targetLanguage: "Structured Text",
    status: "draft",
    createdAt: "2026-05-19T10:00:00Z",
    updatedAt: "2026-05-19T10:00:00Z"
  };
}

function workflowEvent(projectId: string): WorkflowEvent {
  return {
    id: `${projectId}-wf-planning-1`,
    projectId,
    agent: "Planning Agent",
    status: "completed",
    iteration: 1,
    inputSummary: "Requirement accepted",
    outputSummary: "Requirement envelope stored",
    durationMs: 4200,
    createdAt: "2026-05-19T10:00:00Z"
  };
}

function backendPlan(projectId: string): PlanObject {
  return {
    projectId,
    agent: "PlanningAgent/rule_based.v1",
    generatedAt: "2026-05-19T10:00:00Z",
    inputs: [
      {
        name: "Vehicle_Detect",
        type: "BOOL",
        source: "DI-01",
        description: "Vehicle presence detector"
      }
    ],
    outputs: [
      {
        name: "Ped_Walk",
        type: "BOOL",
        address: "DO-04",
        description: "Pedestrian walk indicator"
      }
    ],
    logicRules: ["Implement the controller as an IEC 61131-3 PROGRAM POU"],
    safetyConstraints: ["Conflicting movements must never be active together"],
    scope: {
      standard: "IEC 61131-3",
      edition: "3rd ed. (2013)",
      language: "Structured Text",
      runtime: "CODESYS / TwinCAT compatible"
    }
  };
}


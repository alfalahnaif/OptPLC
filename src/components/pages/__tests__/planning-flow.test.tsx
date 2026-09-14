import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi, type Mock } from "vitest";

import type { PlanObject, Project, RequirementPayload, WorkflowEvent } from "@/lib/api-contracts";
import { deriveRequirementAnalysisPreview } from "@/lib/requirement-analysis";
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
    fireEvent.click(screen.getByRole("button", { name: "Sequential Batch" }));
    fireEvent.click(screen.getByRole("button", { name: /Continue to Requirements/ }));

    await waitFor(() => {
      const payload = JSON.parse((fetchMock.mock.calls[0]?.[1] as { body?: string }).body ?? "{}");
      expect(fetchMock).toHaveBeenCalledWith(
        "http://api.test/api/projects",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining('"complexityTier":"medium"')
        })
      );
      expect(payload.domain).toBe("Sequential Batch");
    });
    await waitFor(() => expect(routerPush()).toHaveBeenCalledWith("/projects/PRJ-0500/requirements"));
  });

  it("requirement submit calls submitRequirements, creates plan, and navigates in real mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = stubFetchByRoute("PRJ-0421");

    render(<RequirementsPage projectId="PRJ-0421" />);
    fireEvent.change(await screen.findByLabelText("Requirement text"), {
      target: {
        value:
          "Control motor start/stop with emergency stop and overload. Include fault lamp indication."
      }
    });
    fireEvent.click(screen.getByRole("button", { name: "Analyze Requirement" }));
    const addInput = screen.getByPlaceholderText("Add a safety property");
    fireEvent.change(addInput, { target: { value: "User safety constraint" } });
    fireEvent.click(screen.getByRole("button", { name: /Add/ }));
    fireEvent.change(screen.getByLabelText("Max scan time"), { target: { value: "9" } });
    fireEvent.change(screen.getByLabelText("Max cyclomatic complexity"), { target: { value: "13" } });
    fireEvent.change(screen.getByLabelText("Min maintainability index"), { target: { value: "81" } });
    fireEvent.click(screen.getByRole("button", { name: /Generate Plan Object/ }));

    await waitFor(() => {
      const submitCall = fetchMock.mock.calls.find(
        ([url, options]) =>
          typeof url === "string" &&
          url.endsWith("/api/projects/PRJ-0421/requirements") &&
          (options as { method?: string } | undefined)?.method === "POST"
      );
      const payload = JSON.parse(((submitCall?.[1] as { body?: string } | undefined)?.body as string | undefined) ?? "{}");
      expect(fetchMock).toHaveBeenCalledWith(
        "http://api.test/api/projects/PRJ-0421/requirements",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining('"projectId":"PRJ-0421"')
        })
      );
      expect(payload.safetyConstraints).toContain("User safety constraint");
      expect(payload.confirmedOutputs ?? []).toEqual([]);
      expect(payload.performanceTargets.maxScanTimeMs).toBe(9);
      expect(payload.performanceTargets.maxCyclomaticComplexity).toBe(13);
      expect(payload.performanceTargets.minMaintainabilityIndex).toBe(81);
      expect(payload.domain).toBe("Motor Control");
      expect(payload.complexityTier).toBe("medium");
    });
    await waitFor(() => expect(routerPush()).toHaveBeenCalledWith("/projects/PRJ-0421/plan"));
  });

  it("submits accepted output and accepted suggested safety constraint only after confirmation", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = stubFetchByRoute("PRJ-0421");

    render(<RequirementsPage projectId="PRJ-0421" />);
    fireEvent.change(await screen.findByLabelText("Requirement text"), {
      target: {
        value: "Control motor with emergency stop and fault lamp indication."
      }
    });
    fireEvent.click(screen.getByRole("button", { name: "Analyze Requirement" }));

    const outputRow = (await screen.findByText(/Fault_Lamp/)).closest(".rounded-md") as HTMLElement | null;
    if (!outputRow) throw new Error("Fault_Lamp suggestion row not found");
    fireEvent.click(within(outputRow).getByRole("button", { name: "Accept" }));

    const safetyRow = (await screen.findByText("Motor_Run must be FALSE when Emergency_Stop is active.")).closest(".flex.items-center.justify-between") as HTMLElement | null;
    if (!safetyRow) throw new Error("Suggested safety row not found");
    fireEvent.click(within(safetyRow).getByRole("button", { name: "Accept" }));

    fireEvent.click(screen.getByRole("button", { name: /Generate Plan Object/ }));

    await waitFor(() => {
      const submitCall = fetchMock.mock.calls.find(
        ([url, options]) =>
          typeof url === "string" &&
          url.endsWith("/api/projects/PRJ-0421/requirements") &&
          (options as { method?: string } | undefined)?.method === "POST"
      );
      const payload = JSON.parse(((submitCall?.[1] as { body?: string } | undefined)?.body as string | undefined) ?? "{}");
      expect(payload.confirmedOutputs).toContain("Fault_Lamp");
      expect(payload.safetyConstraints).toContain("Motor_Run must be FALSE when Emergency_Stop is active.");
    });
  });

  it("does not submit generated safety constraint or suggested output before acceptance", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = stubFetchByRoute("PRJ-0421");

    render(<RequirementsPage projectId="PRJ-0421" />);
    fireEvent.change(await screen.findByLabelText("Requirement text"), {
      target: {
        value: "Sequential batch process with fill valve, mixer motor, drain valve, and batch complete indication."
      }
    });
    fireEvent.click(screen.getByRole("button", { name: "Analyze Requirement" }));
    fireEvent.click(screen.getByRole("button", { name: /Generate Plan Object/ }));

    await waitFor(() => {
      const submitCall = fetchMock.mock.calls.find(
        ([url, options]) =>
          typeof url === "string" &&
          url.endsWith("/api/projects/PRJ-0421/requirements") &&
          (options as { method?: string } | undefined)?.method === "POST"
      );
      const payload = JSON.parse(((submitCall?.[1] as { body?: string } | undefined)?.body as string | undefined) ?? "{}");
      expect(payload.safetyConstraints).not.toContain("Motor_Run must be FALSE when Emergency_Stop is active.");
      expect(payload.confirmedOutputs ?? []).not.toContain("Fill_Valve");
      expect(payload.confirmedOutputs ?? []).not.toContain("Mixer_Motor");
      expect(payload.confirmedOutputs ?? []).not.toContain("Drain_Valve");
      expect(payload.confirmedOutputs ?? []).not.toContain("Batch_Complete");
    });
  });

  it("backend validation error is displayed for blank requirement", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = stubFetchByRoute("PRJ-0421", true);

    render(<RequirementsPage projectId="PRJ-0421" />);
    const textarea = await screen.findByLabelText("Requirement text");
    fireEvent.change(textarea, { target: { value: "   " } });
    fireEvent.click(screen.getByRole("button", { name: /Generate Plan Object/ }));

    expect(await screen.findByText("Requirement submission failed")).toBeInTheDocument();
    expect(await screen.findByText(/Requirement text must not be empty/)).toBeInTheDocument();
    expect(routerPush()).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("plan page calls persisted plan endpoint in real mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = stubFetch(backendPlan("PRJ-0421"));

    render(<PlanPage projectId="PRJ-0421" />);

    expect(await screen.findByText("Rule-Based")).toBeInTheDocument();
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://api.test/api/projects/PRJ-0421/plan",
        expect.objectContaining({ method: "GET" })
      );
    });
    expect(screen.queryByText("Mock Planning Mode")).not.toBeInTheDocument();
    expect(screen.queryByText(/"agent": "PlanningAgent\/v1.4"/)).not.toBeInTheDocument();
  });

  it("mock mode still renders the mock plan without backend fetch", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "true");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<PlanPage projectId="PRJ-0421" />);

    expect(await screen.findByText("Rule-Based")).toBeInTheDocument();
    expect(await screen.findByText(/"agent": "PlanningAgent\/v1.4"/)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("safety constraint remove button removes item", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "true");
    render(<RequirementsPage projectId="PRJ-0421" />);

    const addInput = await screen.findByPlaceholderText("Add a safety property");
    fireEvent.change(addInput, { target: { value: "Temporary constraint" } });
    fireEvent.click(screen.getByRole("button", { name: /Add/ }));
    expect((await screen.findAllByText("Temporary constraint")).length).toBeGreaterThan(0);
    const row = screen.getAllByText("Temporary constraint")[0].closest("div");
    if (!row) throw new Error("Constraint row not found");
    fireEvent.click(within(row).getByRole("button", { name: "Remove" }));
    await waitFor(() => {
      expect(screen.queryByText("Temporary constraint")).not.toBeInTheDocument();
    });
  });

  it("Analyze Requirement produces deterministic suggestions that require acceptance", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "true");
    render(<RequirementsPage projectId="PRJ-0421" />);

    const textarea = await screen.findByLabelText("Requirement text");
    fireEvent.change(textarea, {
      target: {
        value: "Motor start/stop with emergency stop, overload and reset after fault."
      }
    });
    fireEvent.click(screen.getByRole("button", { name: "Analyze Requirement" }));

    expect(await screen.findByText("Motor_Run must be FALSE when Emergency_Stop is active.")).toBeInTheDocument();
    expect(await screen.findByText("Motor_Run must be FALSE when Overload is active.")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "Accept" })[0]);
    expect((await screen.findAllByText("Motor_Run must be FALSE when Emergency_Stop is active.")).length).toBeGreaterThan(0);
  });

  it("preview keeps lamp outputs as suggested until accepted", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "true");
    render(<RequirementsPage projectId="PRJ-0421" />);

    const textarea = await screen.findByLabelText("Requirement text");
    fireEvent.change(textarea, {
      target: {
        value: "Control motor start/stop with E-stop, overload protection, and fault lamp indication."
      }
    });
    fireEvent.click(screen.getByRole("button", { name: "Analyze Requirement" }));

    expect((await screen.findAllByText(/Emergency_Stop/)).length).toBeGreaterThan(0);
    expect(await screen.findByText("Confirmed outputs - 0")).toBeInTheDocument();
    expect(await screen.findByText("Suggested outputs (not yet confirmed)")).toBeInTheDocument();
    expect(await screen.findByText(/Fault_Lamp/)).toBeInTheDocument();
  });

  it("real mode renders backend PlanObject", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    stubFetch(backendPlan("PRJ-0777"));

    render(<PlanPage projectId="PRJ-0777" />);

    expect(await screen.findByText("Vehicle_Detect")).toBeInTheDocument();
    expect(await screen.findByText("Ped_Walk")).toBeInTheDocument();
    expect(await screen.findByText("Conflicting movements must never be active together")).toBeInTheDocument();
    expect(await screen.findByText(/"agent": "PlanningAgent\/rule_based.v1"/)).toBeInTheDocument();
  });

  it("plan page renders only persisted backend PlanObject in real mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const persistedSequentialBatchPlan: PlanObject = {
      projectId: "PRJ-0421",
      agent: "PlanningAgent/real_backend.v2",
      generatedAt: "2026-05-21T08:01:00Z",
      inputs: [
        { name: "Start_PB", type: "BOOL", source: "I0.0", description: "Start push button" },
        { name: "Stop_PB", type: "BOOL", source: "I0.1", description: "Stop push button" }
      ],
      outputs: [
        { name: "Fill_Valve", type: "BOOL", address: "Q0.0", description: "Fill line valve" },
        { name: "Mixer_Motor", type: "BOOL", address: "Q0.1", description: "Mixer drive output" },
        { name: "Drain_Valve", type: "BOOL", address: "Q0.2", description: "Drain valve" }
      ],
      logicRules: [
        "Open Fill_Valve while tank level is below setpoint.",
        "Run Mixer_Motor during mix phase only.",
        "Open Drain_Valve after mix completion."
      ],
      safetyConstraints: [
        "Mixer_Motor must be FALSE when Emergency_Stop is active.",
        "Fill_Valve and Drain_Valve must never be TRUE at the same time."
      ],
      scope: {
        standard: "IEC 61131-3",
        edition: "3rd ed. (2013)",
        language: "Structured Text",
        runtime: "CODESYS / TwinCAT compatible"
      }
    };
    stubFetch(persistedSequentialBatchPlan);

    render(<PlanPage projectId="PRJ-0421" />);

    expect(await screen.findByText("Fill_Valve")).toBeInTheDocument();
    expect(await screen.findByText("Mixer_Motor")).toBeInTheDocument();
    expect(await screen.findByText("Drain_Valve")).toBeInTheDocument();
    expect(screen.queryByText("Motor_Run")).not.toBeInTheDocument();
    expect(await screen.findByText(`Safety SC`)).toBeInTheDocument();
    expect(await screen.findByText(`Safety constraints - ${persistedSequentialBatchPlan.safetyConstraints.length}`)).toBeInTheDocument();
    expect(await screen.findByText(/"name": "Fill_Valve"/)).toBeInTheDocument();
    expect(await screen.findByText(/"name": "Mixer_Motor"/)).toBeInTheDocument();
    expect(await screen.findByText(/"name": "Drain_Valve"/)).toBeInTheDocument();
  });

  it("plan page shows empty state when backend has no persisted plan object", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    stubFetch({ detail: "Plan object for project PRJ-0555 was not found." }, 404);

    render(<PlanPage projectId="PRJ-0555" />);

    expect(await screen.findByText("No PlanObject generated yet.")).toBeInTheDocument();
    expect(screen.queryByText("Loading Plan Object")).not.toBeInTheDocument();
  });

  it("Generate Code button calls backend before navigation", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(backendPlan("PRJ-0421")), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(codeArtifact("PRJ-0421")), { status: 200, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);

    render(<PlanPage projectId="PRJ-0421" />);
    fireEvent.click(await screen.findByRole("button", { name: /^Generate Code/ }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenNthCalledWith(
        2,
        "http://api.test/api/projects/PRJ-0421/generate",
        expect.objectContaining({ method: "POST" })
      );
    });
    await waitFor(() => expect(routerPush()).toHaveBeenCalledWith("/projects/PRJ-0421/code"));
  });

  it("Generate Code button shows error and stays on page on failure", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(backendPlan("PRJ-0421")), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "PlanObject must be generated before code generation." }), { status: 400, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);

    render(<PlanPage projectId="PRJ-0421" />);
    fireEvent.click(await screen.findByRole("button", { name: /^Generate Code/ }));

    expect(await screen.findByText("Code generation failed")).toBeInTheDocument();
    expect(routerPush()).not.toHaveBeenCalledWith("/projects/PRJ-0421/code");
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

function stubFetchByRoute(projectId: string, requirementsNotFound = false) {
  const fetchMock = vi.fn().mockImplementation((url: string, options?: RequestInit) => {
    const method = (options?.method ?? "GET").toUpperCase();
    if (url.endsWith(`/api/projects/${projectId}/requirements`) && method === "GET") {
      if (requirementsNotFound) {
        return Promise.resolve(
          new Response(JSON.stringify({ detail: `Requirements for project ${projectId} were not found.` }), {
            status: 404,
            headers: { "Content-Type": "application/json" }
          })
        );
      }
      return Promise.resolve(
        new Response(JSON.stringify(requirementPayload(projectId)), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        })
      );
    }
    if (url.endsWith(`/api/projects/${projectId}/requirements`) && method === "POST") {
      return Promise.resolve(
        new Response(JSON.stringify(workflowEvent(projectId)), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        })
      );
    }
    if (url.endsWith(`/api/projects/${projectId}/analyze-requirement`) && method === "POST") {
      const body = JSON.parse((options?.body as string | undefined) ?? "{}") as {
        text?: string;
        safetyConstraints?: string[];
      };
      const analysis = deriveRequirementAnalysisPreview({
        projectDomain: projectResponse(projectId).domain,
        requirementText: body.text ?? "",
        safetyConstraints: body.safetyConstraints ?? []
      });
      return Promise.resolve(
        new Response(JSON.stringify(analysis), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        })
      );
    }
    if (url.endsWith(`/api/projects/${projectId}/plan`) && method === "POST") {
      return Promise.resolve(
        new Response(JSON.stringify(backendPlan(projectId)), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        })
      );
    }
    if (url.endsWith(`/api/projects/${projectId}/plan`) && method === "GET") {
      return Promise.resolve(
        new Response(JSON.stringify(backendPlan(projectId)), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        })
      );
    }
    if (url.endsWith(`/api/projects/${projectId}`) && method === "GET") {
      return Promise.resolve(
        new Response(JSON.stringify(projectResponse(projectId)), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        })
      );
    }
    return Promise.resolve(
      new Response(JSON.stringify({ detail: "Unexpected route in test stub" }), {
        status: 404,
        headers: { "Content-Type": "application/json" }
      })
    );
  });
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

function requirementPayload(projectId: string): RequirementPayload {
  return {
    projectId,
    text: "Persisted requirement payload for load tests.",
    safetyConstraints: ["Persisted constraint"],
    confirmedOutputs: [],
    performanceTargets: {
      maxScanTimeMs: 6,
      maxCyclomaticComplexity: 9,
      minMaintainabilityIndex: 74,
      maxIterations: 5
    },
    domain: "Motor Control",
    complexityTier: "medium",
    submittedAt: "2026-05-19T10:00:00Z",
    updatedAt: "2026-05-19T10:00:00Z"
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

function codeArtifact(projectId: string) {
  return {
    projectId,
    artifactId: `${projectId}-code-iter-1`,
    language: "structured-text" as const,
    filename: "plc_prj_0421_controller.st",
    source: "PROGRAM PLC_PRJ_0421_Controller\nEND_PROGRAM",
    iteration: 1,
    generatedAt: "2026-05-19T10:00:00Z",
    metrics: { loc: 2, cyclomaticComplexity: 1, maintainabilityIndex: 89 },
    metadata: {
      generator: "template_based.v1",
      iecStandard: "IEC 61131-3" as const,
      sourcePlanId: projectId,
      createdAt: "2026-05-19T10:00:00Z",
      iteration: 1
    }
  };
}


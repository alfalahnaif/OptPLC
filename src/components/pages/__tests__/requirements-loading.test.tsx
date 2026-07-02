import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { RequirementPayload } from "@/lib/api-contracts";
import { RequirementsPage } from "@/components/pages/requirements-page";

describe("Requirements persisted loading", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("loads persisted requirement data in real mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = stubFetchByPath({
      "/api/projects/PRJ-0421/requirements": { payload: persistedRequirement("PRJ-0421") },
      "/api/projects/PRJ-0421": { payload: persistedProject("PRJ-0421", "Motor Control") }
    });

    render(<RequirementsPage projectId="PRJ-0421" />);

    expect(await screen.findByDisplayValue("Persisted requirement text from backend.")).toBeInTheDocument();
    expect((await screen.findAllByText("Constraint A")).length).toBeGreaterThan(0);
    expect((await screen.findAllByText("Constraint B")).length).toBeGreaterThan(0);
    expect(screen.getByLabelText("Max scan time")).toHaveValue("9");
    expect(screen.getByLabelText("Max cyclomatic complexity")).toHaveValue("11");
    expect(screen.getByLabelText("Min maintainability index")).toHaveValue("72");
    expect(fetchMock).toHaveBeenCalledWith("http://api.test/api/projects/PRJ-0421/requirements", expect.any(Object));
    expect(fetchMock).toHaveBeenCalledWith("http://api.test/api/projects/PRJ-0421", expect.any(Object));
  });

  it("keeps an empty form in real mode when no requirements exist", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = stubFetchByPath({
      "/api/projects/PRJ-0555/requirements": {
        payload: { detail: "Requirements for project PRJ-0555 were not found." },
        status: 404
      },
      "/api/projects/PRJ-0555": { payload: persistedProject("PRJ-0555", "Sequential Batch") }
    });

    render(<RequirementsPage projectId="PRJ-0555" />);

    const textarea = await screen.findByLabelText("Requirement text");
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(textarea).toHaveValue("");
    expect(screen.getByText("No confirmed safety constraints yet.")).toBeInTheDocument();
  });

  it("still uses mock requirement data in mock mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "true");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<RequirementsPage projectId="PRJ-0421" />);

    expect(await screen.findByDisplayValue(/Control a three-phase motor/)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("does not overwrite user edits after persisted data is loaded", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    stubFetchByPath({
      "/api/projects/PRJ-0421/requirements": { payload: persistedRequirement("PRJ-0421") },
      "/api/projects/PRJ-0421": { payload: persistedProject("PRJ-0421", "Motor Control") }
    });

    render(<RequirementsPage projectId="PRJ-0421" />);

    await screen.findByDisplayValue("Persisted requirement text from backend.");
    const textarea = screen.getByLabelText("Requirement text") as HTMLTextAreaElement;

    fireEvent.change(textarea, { target: { value: "Operator edited requirement text." } });
    await waitFor(() => {
      expect(textarea.value).toBe("Operator edited requirement text.");
    });
  });
});

function stubFetchByPath(
  responses: Record<string, { payload: unknown; status?: number }>
) {
  const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input.toString();
    const match = Object.entries(responses).find(([path]) => url.endsWith(path));
    const next = match?.[1] ?? { payload: persistedRequirement("PRJ-0421"), status: 200 };
    return Promise.resolve(
      new Response(JSON.stringify(next.payload), {
        status: next.status ?? 200,
        headers: {
          "Content-Type": "application/json"
        }
      })
    );
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function persistedRequirement(projectId: string): RequirementPayload {
  return {
    projectId,
    text: "Persisted requirement text from backend.",
    safetyConstraints: ["Constraint A", "Constraint B"],
    performanceTargets: {
      maxScanTimeMs: 9,
      maxCyclomaticComplexity: 11,
      minMaintainabilityIndex: 72,
      maxIterations: 6
    },
    domain: "Motor Control",
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

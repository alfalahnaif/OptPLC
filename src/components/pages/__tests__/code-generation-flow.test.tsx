import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CodeArtifact } from "@/lib/api-contracts";
import { CodePage } from "@/components/pages/code-page";

describe("Code Generation frontend flow", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("Code page renders backend-generated Structured Text in real mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    stubFetch(artifact("PRJ-0421"));

    render(<CodePage projectId="PRJ-0421" />);

    expect(await screen.findByText("Real Template Code Generator")).toBeInTheDocument();
    expect(await screen.findByText(/PROGRAM PLC_PRJ_0421_Controller/)).toBeInTheDocument();
    expect(await screen.findByText(/Motor_Run := Run_Cmd/)).toBeInTheDocument();
    expect(await screen.findByText("template_based.v1")).toBeInTheDocument();
  });

  it("missing PlanObject backend error is displayed with guidance", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    stubFetch({ detail: "PlanObject must be generated before code generation." }, 400);

    render(<CodePage projectId="PRJ-0421" />);

    expect(await screen.findByText("Code artifact unavailable")).toBeInTheDocument();
    expect(await screen.findByText("Generate a Plan Object before generating code.")).toBeInTheDocument();
  });

  it("mock mode still renders mock code", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "true");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<CodePage projectId="PRJ-0421" />);

    expect(await screen.findByText("Mock Code Generator")).toBeInTheDocument();
    expect(await screen.findByText(/PROGRAM Motor_Controller/)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
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

function artifact(projectId: string): CodeArtifact {
  return {
    projectId,
    artifactId: `${projectId}-code-iter-1`,
    language: "structured-text",
    filename: "plc_prj_0421_controller.st",
    source: `PROGRAM PLC_PRJ_0421_Controller
VAR_INPUT
    Start_PB : BOOL;
END_VAR
VAR_OUTPUT
    Motor_Run : BOOL;
END_VAR
VAR
    Run_Cmd : BOOL;
END_VAR
Motor_Run := Run_Cmd;
END_PROGRAM`,
    iteration: 1,
    generatedAt: "2026-05-19T10:00:00Z",
    metrics: {
      loc: 11,
      cyclomaticComplexity: 1,
      maintainabilityIndex: 89
    },
    metadata: {
      generator: "template_based.v1",
      iecStandard: "IEC 61131-3",
      sourcePlanId: projectId,
      createdAt: "2026-05-19T10:00:00Z",
      iteration: 1
    }
  };
}

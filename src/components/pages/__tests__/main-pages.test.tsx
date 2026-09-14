import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ProjectRoutePage from "@/app/projects/[id]/page";
import ProjectRequirementsRoutePage from "@/app/projects/[id]/requirements/page";
import { AppShell } from "@/components/layout/app-shell";
import { BenchmarkPage } from "@/components/pages/benchmark-page";
import { CodePage } from "@/components/pages/code-page";
import { DashboardPage } from "@/components/pages/dashboard-page";
import { DebuggingPage } from "@/components/pages/debugging-page";
import { MetricsPage } from "@/components/pages/metrics-page";
import { NewProjectPage } from "@/components/pages/new-project-page";
import { OptimizationPage } from "@/components/pages/optimization-page";
import { PlanPage } from "@/components/pages/plan-page";
import { ReportPage } from "@/components/pages/report-page";
import { RequirementsPage } from "@/components/pages/requirements-page";
import { SettingsPage } from "@/components/pages/settings-page";
import { ValidationPage } from "@/components/pages/validation-page";
import { WorkflowPage } from "@/components/pages/workflow-page";
import { getPlanObject, getProject, validateCode } from "@/lib/api-client";

describe("main frontend pages", () => {
  afterEach(() => {
    (globalThis as unknown as { __nextPathname?: string }).__nextPathname = "/";
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("AppShell renders sidebar navigation", () => {
    render(
      <AppShell>
        <div>workspace</div>
      </AppShell>
    );

    expect(screen.getAllByText("Dashboard")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Requirements")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Benchmark Suite")[0]).toBeInTheDocument();
  });

  it("AppShell header shows current backend project metadata on project routes", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "false");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    (globalThis as unknown as { __nextPathname: string }).__nextPathname = "/projects/PRJ-7777/requirements";
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "PRJ-7777",
          name: "Batch Reactor - B-11",
          description: "Sequential batch process",
          domain: "Sequential Batch",
          standard: "IEC 61131-3",
          targetLanguage: "Structured Text",
          status: "draft",
          createdAt: "2026-05-21T09:00:00Z",
          updatedAt: "2026-05-21T09:00:00Z"
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <AppShell>
        <div>workspace</div>
      </AppShell>
    );

    expect(await screen.findByText("Batch Reactor - B-11")).toBeInTheDocument();
    expect(await screen.findByText("PRJ-7777")).toBeInTheDocument();
  });

  it("Dashboard renders KPI cards", async () => {
    render(<DashboardPage />);

    expect(await screen.findByText("Total projects")).toBeInTheDocument();
    expect(await screen.findByText("Verified programs")).toBeInTheDocument();
    expect(await screen.findByText("Avg complexity reduction")).toBeInTheDocument();
  });

  it("New Project page renders form fields", () => {
    render(<NewProjectPage />);

    expect(screen.getByLabelText("Project name")).toBeInTheDocument();
    expect(screen.getByLabelText("Description")).toBeInTheDocument();
    expect(screen.getByText("Project domain")).toBeInTheDocument();
  });

  it("Requirement Input page renders textarea and example chips", async () => {
    render(<RequirementsPage />);

    expect(await screen.findByDisplayValue(/Control a three-phase motor/)).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Traffic light controller" })).toBeInTheDocument();
  });

  it("Plan page renders Plan Object JSON", async () => {
    render(<PlanPage />);

    expect(await screen.findByText("plan_object.json")).toBeInTheDocument();
    expect(await screen.findByText(/"projectId": "PRJ-0421"/)).toBeInTheDocument();
  });

  it("Workflow page renders all five agents", async () => {
    render(<WorkflowPage />);

    expect(await screen.findByText("Planning Agent")).toBeInTheDocument();
    expect((await screen.findAllByText("Code Generation Agent")).length).toBeGreaterThan(0);
    expect((await screen.findAllByText("Validation Agent")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Debugging Agent")).toBeInTheDocument();
    expect(await screen.findByText("Optimization Agent")).toBeInTheDocument();
  });

  it("Code page renders Monaco wrapper", async () => {
    render(<CodePage />);

    expect(await screen.findByText("motor_controller.st")).toBeInTheDocument();
    expect(await screen.findByTestId("monaco-editor")).toBeInTheDocument();
  });

  it("Validation page renders status badges", async () => {
    render(<ValidationPage />);

    expect(await screen.findByText("All properties hold")).toBeInTheDocument();
    expect((await screen.findAllByText("Passed")).length).toBeGreaterThan(0);
  });

  it("Debugging page renders service-layer patch advice", async () => {
    render(<DebuggingPage />);

    expect(await screen.findByText("Patch advice")).toBeInTheDocument();
    expect(await screen.findByText("Introduce a latched Fault_State variable that survives E-stop recovery.")).toBeInTheDocument();
  });

  it("Optimization page renders optimization passes", async () => {
    render(<OptimizationPage />);

    expect(await screen.findByText("Mock Optimizer")).toBeInTheDocument();
    expect(await screen.findByText("Structural Simplification")).toBeInTheDocument();
    expect(await screen.findByText("Logic Compaction")).toBeInTheDocument();
    expect(await screen.findByText("Maintainability Enhancement")).toBeInTheDocument();
  });

  it("Metrics page renders metric cards and table", async () => {
    render(<MetricsPage />);

    expect(await screen.findByText("Mock Metrics")).toBeInTheDocument();
    expect(await screen.findByText("LOC")).toBeInTheDocument();
    expect(await screen.findByText("Metric-by-metric")).toBeInTheDocument();
  });

  it("Report page renders export buttons", async () => {
    render(<ReportPage />);

    expect(await screen.findByRole("button", { name: /Export JSON/ })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /Export PDF/ })).toBeInTheDocument();
  });

  it("Benchmark page renders benchmark table", async () => {
    render(<BenchmarkPage />);

    expect(await screen.findByText("Benchmark Suite")).toBeInTheDocument();
    expect(await screen.findByText(/Motor start\/stop with E-stop/)).toBeInTheDocument();
  });

  it("Settings page renders configuration sections", async () => {
    render(<SettingsPage />);

    expect(await screen.findByText("Planning Agent")).toBeInTheDocument();
    expect(await screen.findByText("Validation Agent")).toBeInTheDocument();
    expect(await screen.findByText("Optimization Agent")).toBeInTheDocument();
  });

  it("pages can render loading, empty, and error states", () => {
    const { rerender } = render(<DashboardPage state="loading" />);
    expect(screen.getByText("Loading dashboard")).toBeInTheDocument();

    rerender(<DashboardPage state="empty" />);
    expect(screen.getByText("No dashboard metrics")).toBeInTheDocument();

    rerender(<DashboardPage state="error" />);
    expect(within(screen.getByRole("alert")).getByText("Dashboard unavailable")).toBeInTheDocument();
  });

  it("dynamic project route renders project workspace", async () => {
    const route = await ProjectRoutePage({ params: Promise.resolve({ id: "PRJ-0421" }) });
    render(route);

    expect(await screen.findByText("Project envelope")).toBeInTheDocument();
    expect(await screen.findByText("PRJ-0421")).toBeInTheDocument();
  });

  it("dynamic requirements route propagates projectId", async () => {
    const route = await ProjectRequirementsRoutePage({ params: Promise.resolve({ id: "PRJ-9999" }) });
    render(route);

    expect(await screen.findByText("Requirement Input")).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /Generate Plan Object/ })).toHaveAttribute("href", "/projects/PRJ-9999/plan");
  });

  it("page components propagate projectId into service data", async () => {
    render(<PlanPage projectId="PRJ-9999" />);

    expect(await screen.findByText(/"projectId": "PRJ-9999"/)).toBeInTheDocument();
  });

  it("API client returns contract-shaped mock responses", async () => {
    await expect(getProject("PRJ-0421")).resolves.toMatchObject({ id: "PRJ-0421", standard: "IEC 61131-3" });
    await expect(getPlanObject("PRJ-0421")).resolves.toMatchObject({ projectId: "PRJ-0421" });
    await expect(validateCode("PRJ-0421")).resolves.toMatchObject({ projectId: "PRJ-0421", syntaxPassed: true });
  });
});

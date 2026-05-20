"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowRight, Bug, FileDiff, Lightbulb, RotateCcw, TerminalSquare } from "lucide-react";

import { DebuggingModeBadge } from "@/components/common/debugging-mode-badge";
import { PageStateGate, type PageState } from "@/components/common/page-state";
import { RepairLoopPanel } from "@/components/common/repair-loop-panel";
import { PageHeader } from "@/components/layout/page-header";
import { PipelineStrip } from "@/components/layout/pipeline-strip";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { DebuggingReport, RepairLoopReport } from "@/lib/api-contracts";
import { ACTIVE_PROJECT_ID, getDebuggingPageData, projectPath, runRepairLoop, useApiResource } from "@/lib/api-client";

type DebuggingStatus = DebuggingReport["status"];

export function DebuggingPage({ projectId = ACTIVE_PROJECT_ID, state }: { projectId?: string; state?: PageState } = {}) {
  const [repairLoopReport, setRepairLoopReport] = useState<RepairLoopReport | undefined>();
  const [repairLoading, setRepairLoading] = useState(false);
  const [repairError, setRepairError] = useState<string | null>(null);
  const resource = useApiResource(() => getDebuggingPageData(projectId), [projectId]);
  const effectiveState = state ?? resource.state;
  const data = resource.data;
  const report = data?.report;
  const activeRepairLoopReport = repairLoopReport ?? data?.repairLoopReport;
  const stateView =
    effectiveState !== "ready" || !report ? (
      <PageStateGate
        state={effectiveState === "ready" ? "loading" : effectiveState}
        loading={{ title: "Loading debugging feedback", description: "Generating rule-based patch advice from the latest validation report." }}
        empty={{ title: "No debugging feedback", description: "Run validation before requesting debugging advice." }}
        error={{
          title: "Debugging feedback unavailable",
          description: debuggingErrorDescription(resource.error)
        }}
      />
    ) : null;

  return (
    <>
      <PipelineStrip projectId={projectId} />
      <PageHeader
        eyebrow="Pipeline - Step 7 of 9"
        title="Debugging feedback"
        description="Patch advice produced from the latest validation report. Run the repair loop to regenerate Structured Text and revalidate."
        actions={
          <>
            <DebuggingModeBadge />
            {report ? <DebuggingStatusBadge status={report.status} /> : null}
            <Button variant="outline"><RotateCcw /> Replay failure</Button>
            <Button onClick={() => void handleRunRepairLoop()} disabled={repairLoading}>
              {repairLoading ? "Repairing..." : "Run Repair Loop"}
            </Button>
            {report?.status === "NOT_REQUIRED" || activeRepairLoopReport?.finalStatus === "VERIFIED" ? (
              <Button asChild>
                <Link href={projectPath(projectId, "optimization")}>
                  Continue to Optimization <ArrowRight />
                </Link>
              </Button>
            ) : null}
          </>
        }
      />
      {stateView ?? (report ? (
        <div className="space-y-5">
          <DebuggingReportView report={report} />
          {repairError ? (
            <Card className="border-red-200 bg-red-50/30 dark:border-red-900 dark:bg-red-950/10">
              <CardContent className="p-4 text-sm text-red-800 dark:text-red-200">{repairError}</CardContent>
            </Card>
          ) : null}
          {activeRepairLoopReport ? <RepairLoopPanel report={activeRepairLoopReport} /> : null}
        </div>
      ) : null)}
    </>
  );

  async function handleRunRepairLoop() {
    setRepairLoading(true);
    setRepairError(null);
    try {
      setRepairLoopReport(await runRepairLoop(projectId));
    } catch (error) {
      setRepairError(error instanceof Error ? repairLoopErrorDescription(error) : "Repair loop failed.");
    } finally {
      setRepairLoading(false);
    }
  }
}

function DebuggingReportView({ report }: { report: DebuggingReport }) {
  const patchAdvice = report.patchAdvice.length > 0 ? report.patchAdvice : ["No patch advice was generated."];

  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_.9fr]">
      <div className="space-y-5">
        <Card className={report.status === "PATCH_ADVICE_GENERATED" ? "border-amber-200 bg-amber-50/30 dark:border-amber-900 dark:bg-amber-950/10" : ""}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Bug className="size-4 text-amber-700" /> Root cause summary</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <p>{report.rootCauseSummary || report.rootCause}</p>
            <div className="flex flex-wrap gap-2">
              <Badge tone={report.status === "NOT_REQUIRED" ? "success" : report.status === "CANNOT_DEBUG" ? "warning" : "danger"}>{report.sourceValidationStatus}</Badge>
              <Badge tone="neutral">{report.errorType}</Badge>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><FileDiff className="size-4 text-primary" /> Affected code region</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="rounded-md border bg-muted/30 p-3 font-mono text-xs">{report.affectedCodeRegion}</div>
            {report.counterexampleSummary ? (
              <div className="rounded-md border border-red-200 bg-red-50 p-3 text-red-800 dark:border-red-900 dark:bg-red-950/20 dark:text-red-300">
                {report.counterexampleSummary}
              </div>
            ) : (
              <div className="rounded-md border bg-muted/30 p-3 text-muted-foreground">No counterexample summary was required for this report.</div>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="space-y-5">
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Lightbulb className="size-4 text-warning" /> Patch advice</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {patchAdvice.map((item, index) => (
              <div className="flex gap-3 rounded-md border bg-muted/30 p-3 text-sm" key={item}>
                <span className="font-mono text-xs text-muted-foreground">P{index + 1}</span>
                <span>{item}</span>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><TerminalSquare className="size-4 text-primary" /> Suggested regeneration prompt</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm">
            <pre className="whitespace-pre-wrap rounded-md border bg-muted/40 p-3 text-xs">{report.suggestedRegenerationPrompt}</pre>
            <div className="grid gap-2 text-sm">
              <Meta label="Debugger" value={report.debugger} />
              <Meta label="Created" value={formatTimestamp(report.createdAt)} />
              <Meta label="Source artifact" value={report.sourceArtifactId} />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function DebuggingStatusBadge({ status }: { status: DebuggingStatus }) {
  const tone = status === "NOT_REQUIRED" ? "success" : status === "CANNOT_DEBUG" ? "warning" : "danger";
  return <Badge tone={tone} dot>{status}</Badge>;
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right font-medium">{value}</span>
    </div>
  );
}

function debuggingErrorDescription(error: Error | null) {
  const message = error?.message ?? "The debugging report could not be loaded.";
  if (message.includes("ValidationReport must be generated before debugging")) {
    return "Run validation before requesting debugging advice.";
  }
  if (message.includes("CodeArtifact must be generated before debugging")) {
    return "Generate Structured Text code before requesting debugging advice.";
  }
  if (message.includes("PlanObject must be generated before debugging")) {
    return "Generate a Plan Object before requesting debugging advice.";
  }
  return message;
}

function repairLoopErrorDescription(error: Error) {
  const message = error.message;
  if (message.includes("CodeArtifact must be generated before running repair loop")) {
    return "Generate Structured Text code before running the repair loop.";
  }
  if (message.includes("PlanObject must be generated before running repair loop")) {
    return "Generate a Plan Object before running the repair loop.";
  }
  return message;
}

function formatTimestamp(value: string) {
  if (!value) return "Not recorded";
  return value.replace("T", " ").replace("+00:00", " UTC").replace("Z", " UTC");
}

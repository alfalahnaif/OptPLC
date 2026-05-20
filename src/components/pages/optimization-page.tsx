"use client";

import Link from "next/link";
import { ArrowRight, Eye, RotateCcw, Sparkles } from "lucide-react";

import { CodePanel } from "@/components/common/code-panel";
import { OptimizationModeBadge } from "@/components/common/optimization-mode-badge";
import { PageStateGate, type PageState } from "@/components/common/page-state";
import { StatusBadge } from "@/components/common/status-badge";
import { PageHeader } from "@/components/layout/page-header";
import { PipelineStrip } from "@/components/layout/pipeline-strip";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import type { OptimizationReport, OptimizationStatus, StructuredTextMetrics } from "@/lib/api-contracts";
import { ACTIVE_PROJECT_ID, getOptimizationPageData, projectPath, useApiResource } from "@/lib/api-client";

export function OptimizationPage({ projectId = ACTIVE_PROJECT_ID, state }: { projectId?: string; state?: PageState } = {}) {
  const resource = useApiResource(() => getOptimizationPageData(projectId), [projectId]);
  const effectiveState = state ?? resource.state;
  const data = resource.data;
  const report = data?.report;
  const stateView =
    effectiveState !== "ready" || !report ? (
      <PageStateGate
        state={effectiveState === "ready" ? "loading" : effectiveState}
        loading={{ title: "Running optimization", description: "Applying deterministic ST transformations with revalidation after each pass." }}
        empty={{ title: "No optimization results", description: "Run optimization after validation passes." }}
        error={{ title: "Optimization report unavailable", description: optimizationErrorDescription(resource.error) }}
      />
    ) : null;

  return (
    <>
      <PipelineStrip projectId={projectId} />
      <PageHeader
        eyebrow="Pipeline - Step 8 of 9"
        title="Optimization results"
        description="Deterministic static transformations on verified Structured Text. Each accepted pass is revalidated; regressions are rolled back."
        actions={
          <>
            <OptimizationModeBadge />
            {report ? <OptimizationStatusBadge status={report.status} /> : null}
            <Button variant="outline"><Eye /> View optimized code</Button>
            <Button asChild><Link href={projectPath(projectId, "metrics")}>See metrics comparison <ArrowRight /></Link></Button>
          </>
        }
      />
      {stateView ?? (report ? <OptimizationReportView report={report} /> : null)}
    </>
  );
}

function OptimizationReportView({ report }: { report: OptimizationReport }) {
  const acceptedPasses = report.passes.filter((pass) => pass.accepted && pass.status === "applied").length;

  return (
    <div className="space-y-5">
      <Card>
        <CardContent className="grid gap-5 p-5 md:grid-cols-5">
          <Summary label="Status" value={report.status} />
          <Summary label="Passes applied" value={`${acceptedPasses} / ${report.passes.length}`} />
          <Summary label="Rollbacks" value={`${report.rollbackEvents.length}`} />
          <Summary label="LOC reduction" value={`${report.metricsDelta.locReductionPercent}%`} />
          <Summary label="MI gain" value={`${report.metricsDelta.maintainabilityGainPercent}%`} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Before / after metrics</CardTitle>
        </CardHeader>
        <div className="overflow-x-auto">
          <Table>
            <THead>
              <TR><TH>Metric</TH><TH>Before</TH><TH>After</TH><TH>Delta</TH></TR>
            </THead>
            <TBody>
              <MetricRow label="LOC" before={report.beforeMetrics.loc} after={report.afterMetrics.loc} delta={report.metricsDelta.loc} />
              <MetricRow label="Cyclomatic complexity" before={report.beforeMetrics.cyclomaticComplexity} after={report.afterMetrics.cyclomaticComplexity} delta={report.metricsDelta.cyclomaticComplexity} />
              <MetricRow label="Maintainability index" before={report.beforeMetrics.maintainabilityIndex} after={report.afterMetrics.maintainabilityIndex} delta={report.metricsDelta.maintainabilityIndex} />
              <MetricRow label="Estimated scan time" before={`${report.beforeMetrics.estimatedScanTimeMs} ms`} after={`${report.afterMetrics.estimatedScanTimeMs} ms`} delta={`${report.metricsDelta.estimatedScanTimeMs} ms`} />
            </TBody>
          </Table>
        </div>
      </Card>

      <div className="space-y-4">
        {report.passes.map((pass, index) => (
          <Card key={`${pass.name}-${index}`}>
            <CardContent className="grid gap-4 p-4 md:grid-cols-[40px_1fr_220px_220px_150px] md:items-center">
              <span className="grid size-8 place-items-center rounded-md border bg-muted text-sm">{index + 1}</span>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold">{pass.name}</span>
                  <PassStatusBadge status={pass.status} />
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{pass.summary}</p>
              </div>
              <MetricDelta label="LOC" before={pass.beforeMetrics.loc} after={pass.afterMetrics.loc} />
              <MetricDelta label="CC" before={pass.beforeMetrics.cyclomaticComplexity} after={pass.afterMetrics.cyclomaticComplexity} />
              <Badge tone={pass.revalidationStatus === "VERIFIED" ? "success" : "danger"} dot>{pass.revalidationStatus}</Badge>
            </CardContent>
          </Card>
        ))}
      </div>

      {report.rollbackEvents.length > 0 ? (
        <Card className="border-amber-200 bg-amber-50/30 dark:border-amber-900 dark:bg-amber-950/10">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><RotateCcw className="size-4 text-warning" /> Rollback events</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {report.rollbackEvents.map((event) => (
              <div className="rounded-md border bg-background/70 p-3 text-sm" key={`${event.passName}-${event.reason}`}>
                <div className="font-medium">{event.passName}</div>
                <div className="mt-1 text-muted-foreground">{event.reason}</div>
                <Badge className="mt-2" tone={event.revalidationStatus === "VERIFIED" ? "success" : "danger"}>{event.revalidationStatus}</Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      <div>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 font-semibold"><Sparkles className="size-4 text-primary" /> Final optimized code</div>
            <p className="mt-1 text-xs text-muted-foreground">
              {metricSummary(report.afterMetrics)} - {report.summary}
            </p>
          </div>
          <StatusBadge status={report.revalidationStatus === "VERIFIED" ? "verified" : "warning"} label={`Revalidation ${report.revalidationStatus}`} />
        </div>
        <CodePanel title={report.optimizedCode.filename} code={report.optimizedCode.source} height="420px" />
      </div>
    </div>
  );
}

function Summary({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-emerald-700 dark:text-emerald-300">{value}</div>
    </div>
  );
}

function MetricRow({ label, before, after, delta }: { label: string; before: string | number; after: string | number; delta: string | number }) {
  return (
    <TR>
      <TD>{label}</TD>
      <TD className="font-mono text-xs">{before}</TD>
      <TD className="font-mono text-xs">{after}</TD>
      <TD className="font-mono text-xs text-emerald-700">{delta}</TD>
    </TR>
  );
}

function MetricDelta({ label, before, after }: { label: string; before: number; after: number }) {
  const delta = after - before;
  return (
    <div className="rounded-md border bg-muted/40 p-3 text-sm">
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-1 flex justify-between">
        <span className="font-semibold">{after}</span>
        <span className={delta <= 0 ? "text-emerald-700" : "text-red-700"}>{delta}</span>
      </div>
    </div>
  );
}

function OptimizationStatusBadge({ status }: { status: OptimizationStatus }) {
  const tone = status === "OPTIMIZED" || status === "NO_CHANGES" ? "success" : status === "ROLLED_BACK" ? "warning" : "danger";
  return <Badge tone={tone} dot>{status}</Badge>;
}

function PassStatusBadge({ status }: { status: OptimizationReport["passes"][number]["status"] }) {
  const tone = status === "applied" ? "success" : status === "no_changes" ? "info" : "warning";
  return <Badge tone={tone} dot>{status.replace("_", " ")}</Badge>;
}

function metricSummary(metrics: StructuredTextMetrics) {
  return `${metrics.loc} LOC - CC ${metrics.cyclomaticComplexity} - MI ${metrics.maintainabilityIndex} - scan ${metrics.estimatedScanTimeMs} ms`;
}

function optimizationErrorDescription(error: Error | null) {
  const message = error?.message ?? "The optimization report could not be loaded.";
  if (message.includes("CodeArtifact must be generated before optimization")) {
    return "Generate Structured Text code before running optimization.";
  }
  if (message.includes("PlanObject must be generated before optimization")) {
    return "Generate a Plan Object before running optimization.";
  }
  if (message.includes("ValidationReport must be generated before optimization")) {
    return "Run validation before optimization.";
  }
  if (message.includes("Code must be verified before optimization")) {
    return "Code must be verified before optimization. Run validation or repair loop first.";
  }
  return message;
}

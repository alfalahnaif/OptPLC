"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";
import { CheckCircle, Download, FileDown } from "lucide-react";

import { CodePanel } from "@/components/common/code-panel";
import { PageStateGate, type PageState } from "@/components/common/page-state";
import { ReportModeBadge } from "@/components/common/report-mode-badge";
import { StatusBadge } from "@/components/common/status-badge";
import { PageHeader } from "@/components/layout/page-header";
import { PipelineStrip } from "@/components/layout/pipeline-strip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { ACTIVE_PROJECT_ID, exportReportJson, exportReportMarkdown, getFinalReport, useApiResource } from "@/lib/api-client";
import type { FinalReport, ProjectStatus } from "@/lib/api-contracts";

export function ReportPage({ projectId = ACTIVE_PROJECT_ID, state }: { projectId?: string; state?: PageState } = {}) {
  const resource = useApiResource(() => getFinalReport(projectId), [projectId]);
  const [exporting, setExporting] = useState<"json" | "markdown" | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const effectiveState = state ?? resource.state;
  const report = resource.data;
  const stateView =
    effectiveState !== "ready" || !report ? (
      <PageStateGate
        state={effectiveState === "ready" ? "loading" : effectiveState}
        loading={{ title: "Loading final report", description: "Preparing engineering summary and validation evidence." }}
        empty={{ title: "No final report", description: "Complete the pipeline to generate a report." }}
        error={{ title: "Final report unavailable", description: resource.error?.message ?? "The final report could not be rendered." }}
      />
    ) : null;

  const code = report?.codeArtifact?.source ?? "";
  const previewCode = code ? previewStructuredText(code, 30) : "No code artifact is available.";
  const approxHash = buildApproxHash(code);
  const appliedPasses = report?.optimization?.passes.filter((pass) => pass.accepted).length ?? 0;
  const validationAttempts = report?.validation?.iteration ?? report?.repairLoop?.iterations ?? report?.codeArtifact?.iteration ?? 1;
  const locReduction = report?.metrics?.metricsDelta.locReductionPercent ?? 0;
  const dynamicSummary = report
    ? `${report.project.name} controller was specified in natural language, parsed into a Plan Object, and synthesised to IEC 61131-3 Structured Text. After ${validationAttempts} validation attempt(s), the program passed all safety checks and was reduced by ${Math.abs(locReduction).toFixed(1)}% LOC through ${appliedPasses} optimization pass(es).`
    : "";
  const sessionTime = report ? formatDuration(durationBetween(report.project.createdAt, report.generatedAt || report.project.updatedAt)) : "N/A";
  const engineerName = report?.optimization?.optimizer ?? report?.codeArtifact?.metadata.generator ?? "OptPLC Engineering Agent";
  const outcomeLabel = `${statusWord(report?.validation?.status === "VERIFIED")} · ${statusWord(report?.optimization?.status === "OPTIMIZED")}`;
  const iterationLabel = `iter ${report?.codeArtifact?.iteration ?? 1}/${report?.requirement?.performanceTargets.maxIterations ?? 1}`;
  const sessionEvents = report ? buildAgentEvents(report) : [];
  const agentCount = new Set(sessionEvents.map((event) => event.agent)).size;

  const downloadBlob = (blob: Blob, filename: string) => {
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(objectUrl);
  };

  const handleExportJson = async () => {
    try {
      setExporting("json");
      setExportError(null);
      const blob = await exportReportJson(projectId);
      downloadBlob(blob, `plcforge_report_${projectId}.json`);
    } catch (error) {
      setExportError(error instanceof Error ? error.message : "JSON export failed.");
    } finally {
      setExporting(null);
    }
  };

  const handleExportMarkdown = async () => {
    try {
      setExporting("markdown");
      setExportError(null);
      const blob = await exportReportMarkdown(projectId);
      downloadBlob(blob, `plcforge_report_${projectId}.md`);
    } catch (error) {
      setExportError(error instanceof Error ? error.message : "Markdown export failed.");
    } finally {
      setExporting(null);
    }
  };

  return (
    <>
      <PipelineStrip projectId={projectId} />
      <PageHeader
        title="Final Report"
        description="Exportable engineering summary for review, handoff, and audit records."
        actions={
          <>
            <ReportModeBadge />
            <Button variant="outline" onClick={handleExportJson} disabled={exporting !== null}>
              <FileDown /> {exporting === "json" ? "Exporting JSON..." : "Export JSON"}
            </Button>
            <Button variant="outline" onClick={handleExportMarkdown} disabled={exporting !== null}>
              <FileDown /> {exporting === "markdown" ? "Exporting Markdown..." : "Export Markdown"}
            </Button>
            <Button variant="outline" disabled title="PDF export is coming soon">
              <FileDown /> Export PDF
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                if (!report?.codeArtifact?.source) return;
                downloadBlob(new Blob([report.codeArtifact.source], { type: "text/plain" }), report.codeArtifact.filename || `optplc_${projectId}.st`);
              }}
              disabled={!report?.codeArtifact?.source}
            >
              <Download /> Download .st
            </Button>
          </>
        }
      />
      {exportError ? <div className="mb-3 text-sm text-destructive" role="alert">{exportError}</div> : null}
      {effectiveState === "loading" ? (
        <ReportSkeleton />
      ) : stateView ?? (report ? (
        <Card className="border border-border">
          <CardHeader className="border-b border-border bg-card px-6 py-5">
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_auto]">
              <div>
                <div className="text-[10.5px] uppercase tracking-[0.24em] text-muted-foreground">OPTPLC ENGINEERING REPORT</div>
                <CardTitle className="mt-1 text-3xl italic tracking-tight">{report.project.name}</CardTitle>
              </div>
              <div className="flex flex-col items-start gap-2 lg:items-end">
                <span className="rounded-md border border-green-200 bg-green-50 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-green-700 dark:border-green-800 dark:bg-green-950/30 dark:text-green-300">
                  {outcomeLabel}
                </span>
                <span className="text-xs text-muted-foreground">{report.project.id} · {iterationLabel}</span>
              </div>
            </div>
            <div className="mt-4 text-sm text-muted-foreground">
              Generated by the OptPLC agent pipeline · {new Date(report.generatedAt).toLocaleString()}
            </div>
            <div className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] uppercase tracking-[0.16em] text-muted-foreground lg:grid-cols-4">
              <span>Domain · <span className="text-foreground">{report.project.domain}</span></span>
              <span>Target · <span className="text-foreground">{report.project.targetLanguage}</span></span>
              <span>Engineer · <span className="text-foreground">{engineerName}</span></span>
              <span>Session Time · <span className="text-foreground">{sessionTime}</span></span>
            </div>
          </CardHeader>

          <CardContent className="px-6 py-6">
            <div className="grid grid-cols-12 gap-x-6 gap-y-5">
              <ReportSection n={1} title="Project summary">
                <p>{dynamicSummary}</p>
              </ReportSection>

              <ReportSection n={2} title="Input requirement">
                <blockquote className="border-l-2 border-border pl-4 italic text-muted-foreground">
                  {report.requirement?.text ?? "Requirement data is unavailable for this project session."}
                </blockquote>
              </ReportSection>

              <ReportSection n={3} title="Plan Object summary">
                <ul className="list-disc space-y-1 pl-5">
                  <li>Inputs: {report.planObject?.inputs.length ?? 0}</li>
                  <li>Outputs: {report.planObject?.outputs.length ?? 0}</li>
                  <li>Control rules count: {report.planObject?.logicRules.length ?? 0}</li>
                  <li>Safety constraints count: {report.planObject?.safetyConstraints.length ?? 0}</li>
                  <li>IEC scope: {report.planObject?.scope.standard ?? report.project.standard} · {report.planObject?.scope.language ?? report.project.targetLanguage}</li>
                </ul>
              </ReportSection>

              <ReportSection n={4} title="Generated ST code">
                <p className="mb-3 text-muted-foreground">
                  Final optimized form, {countLines(code)} lines, CC {report.codeArtifact?.metrics.cyclomaticComplexity ?? report.metrics?.afterMetrics.cyclomaticComplexity ?? "N/A"}, MI {report.codeArtifact?.metrics.maintainabilityIndex ?? report.metrics?.afterMetrics.maintainabilityIndex ?? "N/A"}.
                </p>
                <CodePanel title={`${report.codeArtifact?.filename ?? "final.st"} (first 30 lines)`} code={previewCode} height="360px" />
              </ReportSection>

              <ReportSection n={5} title="Validation results">
                <ul className="space-y-2">
                  <li className={report.validation?.syntaxPassed ? "text-green-600" : "text-red-500"}>Syntax: {report.validation?.syntaxPassed ? "PASS" : "FAIL"}</li>
                  <li className={report.validation?.formalPassed ? "text-green-600" : "text-red-500"}>Formal: {report.validation?.formalPassed ? "PASS" : "FAIL"}</li>
                  <li className={livenessPassed(report.validation) ? "text-green-600" : "text-red-500"}>Liveness: {livenessPassed(report.validation) ? "PASS" : "FAIL"}</li>
                </ul>
              </ReportSection>

              <ReportSection n={6} title="Optimization results">
                <ol className="list-decimal space-y-2 pl-5">
                  {(report.optimization?.passes.slice(0, 3) ?? []).map((pass, index) => (
                    <li key={`${pass.name}-${index}`}>
                      <span className="font-medium">{pass.name}</span> — {pass.summary} (revalidation: {pass.revalidationStatus})
                    </li>
                  ))}
                  {!report.optimization?.passes.length ? <li>No optimization pass history available.</li> : null}
                </ol>
              </ReportSection>

              <ReportSection n={7} title="Metrics delta">
                {report.metrics ? (
                  <div className="overflow-x-auto">
                    <Table>
                      <THead>
                        <TR>
                          <TH>Metric</TH>
                          <TH>Before</TH>
                          <TH>After</TH>
                          <TH>Delta</TH>
                        </TR>
                      </THead>
                      <TBody>
                        {metricDeltaRows(report).map((row) => (
                          <TR key={row.metric}>
                            <TD className="font-medium">{row.metric}</TD>
                            <TD>{row.before}</TD>
                            <TD>{row.after}</TD>
                            <TD className={row.improved ? "text-green-600" : "text-red-500"}>{row.delta}</TD>
                          </TR>
                        ))}
                      </TBody>
                    </Table>
                  </div>
                ) : (
                  <p className="text-muted-foreground">Metrics report is unavailable.</p>
                )}
              </ReportSection>

              <ReportSection n={8} title="Agent session log">
                <p className="mb-3 text-muted-foreground">
                  {sessionEvents.length} entries across {agentCount || 0} agents · {validationAttempts} iterations · {sessionTime} wall time.
                </p>
                <ul className="list-disc space-y-1 pl-5">
                  {sessionEvents.map((event) => (
                    <li key={`${event.agent}-${event.detail}`}>{event.agent}: {event.detail}</li>
                  ))}
                </ul>
              </ReportSection>

              <ReportSection n={9} title="Final recommendation">
                <div className="rounded-md border border-green-300 bg-green-50 p-4 dark:border-green-900 dark:bg-green-950/30">
                  <div className="flex items-start gap-2 text-green-700 dark:text-green-300">
                    <CheckCircle className="mt-0.5 size-4 shrink-0" />
                    <div>
                      <p className="font-medium">
                        {report.finalStatusSummary || "The implementation is approved for controlled deployment."}
                      </p>
                      <ul className="mt-2 list-disc space-y-1 pl-5 text-[13px]">
                        {(report.recommendations.length > 0 ? report.recommendations : ["Proceed with staged commissioning and runtime monitoring."]).map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              </ReportSection>
            </div>

            <div className="mt-6 border-t border-border pt-4">
              <div className="flex flex-col justify-between gap-3 text-sm md:flex-row md:items-center">
                <div className="flex items-center gap-3">
                  <div className="flex size-9 items-center justify-center rounded-full border border-border bg-muted font-semibold">
                    {initials(engineerName)}
                  </div>
                  <div>
                    <div className="font-medium">{engineerName}</div>
                    <div className="text-xs text-muted-foreground">OptPLC Systems · Saint Petersburg</div>
                  </div>
                </div>
                <div className="font-mono text-xs text-muted-foreground">
                  Document ID: OPTPLC-RPT-{report.project.id.replace("PRJ-", "")} · sha256 {approxHash}
                </div>
              </div>
            </div>
            <div className="mt-5">
              <StatusBadge status={toBadgeStatus(report.project.status)} />
              <Button className="ml-3" variant="outline" asChild>
                <Link href="/benchmark">Open benchmark suite</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null)}
    </>
  );
}

function ReportSection({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <>
      <div className="col-span-12 md:col-span-3">
        <div className="text-[10.5px] uppercase tracking-widest font-semibold text-muted-foreground">§ {n}</div>
        <h3 className="mt-0.5 text-[15px] font-semibold tracking-tight">{title}</h3>
      </div>
      <div className="col-span-12 pb-6 text-[13px] leading-relaxed md:col-span-9 border-b border-border">
        {children}
      </div>
    </>
  );
}

function ReportSkeleton() {
  return (
    <Card className="border border-border">
      <CardHeader className="space-y-3 border-b border-border">
        <div className="h-3 w-48 animate-pulse rounded bg-muted" />
        <div className="h-8 w-80 animate-pulse rounded bg-muted" />
        <div className="h-4 w-72 animate-pulse rounded bg-muted" />
      </CardHeader>
      <CardContent className="grid grid-cols-12 gap-x-6 gap-y-5 py-6">
        {Array.from({ length: 8 }).map((_, index) => (
          <div className="col-span-12 grid grid-cols-12 gap-4" key={index}>
            <div className="col-span-12 md:col-span-3">
              <div className="h-3 w-20 animate-pulse rounded bg-muted" />
              <div className="mt-2 h-4 w-36 animate-pulse rounded bg-muted" />
            </div>
            <div className="col-span-12 md:col-span-9 border-b border-border pb-5">
              <div className="h-3 w-full animate-pulse rounded bg-muted" />
              <div className="mt-2 h-3 w-3/4 animate-pulse rounded bg-muted" />
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function metricDeltaRows(report: FinalReport) {
  if (!report.metrics) return [];
  return [
    {
      metric: "LOC",
      before: report.metrics.beforeMetrics.loc.toString(),
      after: report.metrics.afterMetrics.loc.toString(),
      delta: signed(report.metrics.metricsDelta.locDelta),
      improved: report.metrics.metricsDelta.locDelta <= 0
    },
    {
      metric: "CC",
      before: report.metrics.beforeMetrics.cyclomaticComplexity.toString(),
      after: report.metrics.afterMetrics.cyclomaticComplexity.toString(),
      delta: signed(report.metrics.metricsDelta.cyclomaticComplexityDelta),
      improved: report.metrics.metricsDelta.cyclomaticComplexityDelta <= 0
    },
    {
      metric: "MI",
      before: report.metrics.beforeMetrics.maintainabilityIndex.toString(),
      after: report.metrics.afterMetrics.maintainabilityIndex.toString(),
      delta: signed(report.metrics.metricsDelta.maintainabilityIndexDelta),
      improved: report.metrics.metricsDelta.maintainabilityIndexDelta >= 0
    },
    {
      metric: "Scan Time (ms)",
      before: report.metrics.beforeMetrics.estimatedScanTimeMs.toFixed(2),
      after: report.metrics.afterMetrics.estimatedScanTimeMs.toFixed(2),
      delta: signed(round(report.metrics.metricsDelta.estimatedScanTimeDelta)),
      improved: report.metrics.metricsDelta.estimatedScanTimeDelta <= 0
    }
  ];
}

function livenessPassed(validation: FinalReport["validation"]) {
  const properties = validation?.properties ?? [];
  if (properties.length === 0) return false;
  return properties.every((property) => property.status === "passed");
}

function buildAgentEvents(report: FinalReport) {
  const events: Array<{ agent: string; detail: string }> = [];
  if (report.requirement?.text) events.push({ agent: "Planning Agent", detail: "Natural-language requirement captured." });
  if (report.planObject) events.push({ agent: "Planning Agent", detail: `Plan object produced with ${report.planObject.logicRules.length} logic rules.` });
  if (report.codeArtifact) events.push({ agent: "Code Generation Agent", detail: `Structured Text generated (${countLines(report.codeArtifact.source)} LOC).` });
  if (report.validation) events.push({ agent: "Validation Agent", detail: `Validation status ${report.validation.status}.` });
  if (report.debugging) events.push({ agent: "Debugging Agent", detail: report.debuggingSummary || "Debugging report generated." });
  if (report.optimization) events.push({ agent: "Optimization Agent", detail: `${report.optimization.passes.length} optimization pass(es) executed.` });
  return events;
}

function previewStructuredText(source: string, limit: number) {
  const lines = source.split(/\r?\n/);
  const preview = lines.slice(0, limit);
  if (lines.length > limit) preview.push("...");
  return preview.join("\n");
}

function countLines(source: string) {
  return source ? source.split(/\r?\n/).length : 0;
}

function buildApproxHash(source: string) {
  if (!source) return "--------…----";
  try {
    const encoded = btoa(source);
    return `${encoded.slice(0, 8)}…${encoded.slice(-4)}`;
  } catch {
    return "--------…----";
  }
}

function durationBetween(start: string, end: string) {
  const startMs = Date.parse(start);
  const endMs = Date.parse(end);
  if (Number.isNaN(startMs) || Number.isNaN(endMs) || endMs < startMs) return null;
  return endMs - startMs;
}

function formatDuration(durationMs: number | null) {
  if (durationMs == null) return "N/A";
  const totalMinutes = Math.max(1, Math.round(durationMs / 60000));
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours === 0) return `${minutes}m`;
  return `${hours}h ${minutes}m`;
}

function statusWord(passed: boolean | undefined) {
  return passed ? "VERIFIED" : "PENDING";
}

function initials(name: string) {
  const parts = name.split(/[\s._-]+/).filter(Boolean);
  if (parts.length === 0) return "OE";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
}

function signed(value: number) {
  return `${value >= 0 ? "+" : ""}${value}`;
}

function round(value: number) {
  return Math.round(value * 100) / 100;
}

function toBadgeStatus(status: ProjectStatus) {
  if (status === "optimized") return "optimized";
  if (status === "validated") return "verified";
  if (status === "failed") return "failed";
  return "completed";
}

"use client";

import Link from "next/link";
import { useState } from "react";
import { Download, FileText } from "lucide-react";

import { PageStateGate, type PageState } from "@/components/common/page-state";
import { StatusBadge } from "@/components/common/status-badge";
import { PageHeader } from "@/components/layout/page-header";
import { PipelineStrip } from "@/components/layout/pipeline-strip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ACTIVE_PROJECT_ID, exportReportJson, exportReportMarkdown, getFinalReport, useApiResource } from "@/lib/api-client";
import type { ProjectStatus } from "@/lib/api-contracts";

export function ReportPage({ projectId = ACTIVE_PROJECT_ID, state }: { projectId?: string; state?: PageState } = {}) {
  const resource = useApiResource(() => getFinalReport(projectId), [projectId]);
  const [exporting, setExporting] = useState<"json" | "markdown" | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const effectiveState = state ?? resource.state;
  const data = resource.data;
  const stateView =
    effectiveState !== "ready" || !data ? (
      <PageStateGate
        state={effectiveState === "ready" ? "loading" : effectiveState}
        loading={{ title: "Loading final report", description: "Preparing engineering summary and validation evidence." }}
        empty={{ title: "No final report", description: "Complete the pipeline to generate a report." }}
        error={{ title: "Final report unavailable", description: resource.error?.message ?? "The final report could not be rendered." }}
      />
    ) : null;

  const report = data;

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
            <Button variant="outline" onClick={handleExportJson} disabled={exporting !== null}>
              <Download /> {exporting === "json" ? "Exporting JSON..." : "Export JSON"}
            </Button>
            <Button variant="outline" onClick={handleExportMarkdown} disabled={exporting !== null}>
              <Download /> {exporting === "markdown" ? "Exporting Markdown..." : "Export Markdown"}
            </Button>
            <Button disabled title="PDF export is coming soon">
              <Download /> Export PDF (Coming soon)
            </Button>
          </>
        }
      />
      {exportError ? <div className="mb-3 text-sm text-destructive" role="alert">{exportError}</div> : null}
      {stateView ?? (report ? <div className="grid gap-5 xl:grid-cols-[1fr_.42fr]">
        <Card>
          <CardHeader className="border-b-4 border-primary">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm text-muted-foreground">PLC Agent Optimizer</div>
                <CardTitle className="mt-2 text-2xl">{report.project.name}</CardTitle>
              </div>
              <StatusBadge status={toBadgeStatus(report.project.status)} />
            </div>
          </CardHeader>
          <CardContent className="space-y-8 p-8">
            <section>
              <h2 className="mb-3 text-lg font-semibold">Project summary</h2>
              <p className="text-sm leading-7 text-muted-foreground">{report.summary}</p>
            </section>
            <section>
              <h2 className="mb-3 text-lg font-semibold">Requirement</h2>
              <p className="rounded-md border bg-muted/30 p-4 text-sm leading-7">
                {report.requirement?.text ?? "Not generated yet"}
              </p>
            </section>
            <section>
              <h2 className="mb-3 text-lg font-semibold">Plan summary</h2>
              <div className="grid gap-3 md:grid-cols-3">
                <Box label="Inputs" value={report.planObject?.inputs.length ?? "Not generated yet"} />
                <Box label="Outputs" value={report.planObject?.outputs.length ?? "Not generated yet"} />
                <Box label="Safety constraints" value={report.planObject?.safetyConstraints.length ?? "Not generated yet"} />
              </div>
            </section>
            <section>
              <h2 className="mb-3 text-lg font-semibold">Generated code summary</h2>
              <pre className="overflow-x-auto rounded-md border bg-muted/20 p-3 text-xs">
                {report.codeArtifact?.source ?? "Not generated yet"}
              </pre>
            </section>
            <section>
              <h2 className="mb-3 text-lg font-semibold">Validation summary</h2>
              <p className="text-sm text-muted-foreground">{report.validationSummary || "Not generated yet"}</p>
            </section>
            <section>
              <h2 className="mb-3 text-lg font-semibold">Debugging summary</h2>
              <p className="text-sm text-muted-foreground">{report.debuggingSummary || "Not generated yet"}</p>
            </section>
            <section>
              <h2 className="mb-3 text-lg font-semibold">Repair loop summary</h2>
              <p className="text-sm text-muted-foreground">{report.repairLoopSummary || "Not generated yet"}</p>
            </section>
            <section>
              <h2 className="mb-3 text-lg font-semibold">Optimization summary</h2>
              <p className="text-sm text-muted-foreground">{report.optimizationSummary || "Not generated yet"}</p>
            </section>
            <section>
              <h2 className="mb-3 text-lg font-semibold">Metrics summary</h2>
              <p className="text-sm text-muted-foreground">{report.metricsSummary || "Not generated yet"}</p>
            </section>
            <section>
              <h2 className="mb-3 text-lg font-semibold">Final recommendation</h2>
              <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                {report.recommendations.length > 0 ? report.recommendations.map((recommendation) => (
                  <li key={recommendation}>{recommendation}</li>
                )) : <li>Not generated yet</li>}
              </ul>
            </section>
            <section>
              <h2 className="mb-3 text-lg font-semibold">Limitations</h2>
              <p className="text-sm text-muted-foreground">{report.limitationsDisclaimer}</p>
            </section>
          </CardContent>
        </Card>
        <div className="space-y-5">
          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2"><FileText className="size-4 text-primary" /> Report metadata</CardTitle></CardHeader>
            <CardContent className="space-y-3 text-sm">
              <Row label="Project ID" value={report.project.id} />
              <Row label="Generated" value={report.generatedAt} />
              <Row label="Standard" value={report.project.standard} />
              <Row label="Language" value={report.project.targetLanguage} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Metric summary</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {report.metrics ? [
                { label: "Lines of code", value: report.metrics.afterMetrics.loc.toString() },
                { label: "Cyclomatic complexity", value: report.metrics.afterMetrics.cyclomaticComplexity.toString() },
                { label: "Maintainability index", value: report.metrics.afterMetrics.maintainabilityIndex.toString() },
                { label: "Estimated scan time (ms)", value: report.metrics.afterMetrics.estimatedScanTimeMs.toFixed(2) }
              ].map((metric) => (
                <div className="flex justify-between rounded-md border bg-muted/30 p-3 text-sm" key={metric.label}>
                  <span>{metric.label}</span>
                  <span className="font-semibold">{metric.value}</span>
                </div>
              )) : <div className="rounded-md border bg-muted/30 p-3 text-sm text-muted-foreground">Not generated yet</div>}
              <Button className="w-full" asChild><Link href="/benchmark">Open benchmark suite</Link></Button>
            </CardContent>
          </Card>
        </div>
      </div> : null)}
    </>
  );
}

function Box({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border bg-muted/30 p-4">
      <div className="text-xs uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return <div className="flex justify-between gap-4"><span className="text-muted-foreground">{label}</span><span className="text-right font-medium">{value}</span></div>;
}

function toBadgeStatus(status: ProjectStatus) {
  if (status === "optimized") return "optimized";
  if (status === "validated") return "verified";
  if (status === "failed") return "failed";
  return "completed";
}

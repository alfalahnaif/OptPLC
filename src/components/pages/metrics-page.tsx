"use client";

import Link from "next/link";
import { ArrowRight, Download, TrendingDown, TrendingUp } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import { MetricsModeBadge } from "@/components/common/metrics-mode-badge";
import { PageStateGate, type PageState } from "@/components/common/page-state";
import { PageHeader } from "@/components/layout/page-header";
import { PipelineStrip } from "@/components/layout/pipeline-strip";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { ACTIVE_PROJECT_ID, getMetricsPageData, projectPath, useApiResource, type MetricsPageData } from "@/lib/api-client";

export function MetricsPage({ projectId = ACTIVE_PROJECT_ID, state }: { projectId?: string; state?: PageState } = {}) {
  const resource = useApiResource(() => getMetricsPageData(projectId), [projectId]);
  const effectiveState = state ?? resource.state;
  const data = resource.data;
  const stateView =
    effectiveState !== "ready" || !data ? (
      <PageStateGate
        state={effectiveState === "ready" ? "loading" : effectiveState}
        loading={{ title: "Loading metrics comparison", description: "Preparing before and after optimization metrics." }}
        empty={{ title: "No metrics available", description: "Generate code and run metrics/optimization before viewing metrics." }}
        error={{ title: "Metrics unavailable", description: resource.error?.message ?? "Generate code and run metrics/optimization before viewing metrics." }}
      />
    ) : null;

  return (
    <>
      <PipelineStrip projectId={projectId} />
      <PageHeader
        eyebrow="Pipeline - Step 9 of 9"
        title="Metrics comparison"
        description="Before and after on the same project. Optimization is conservative: every gain is confirmed by validation."
        actions={
          <>
            <MetricsModeBadge />
            <Button variant="outline"><Download /> Export CSV</Button>
            <Button asChild><Link href={projectPath(projectId, "report")}>Generate report <ArrowRight /></Link></Button>
          </>
        }
      />
      {stateView ?? (data ? (
        <>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {headlineMetrics(data).map((metric) => {
          const improving = metric.isImprovement;
          return (
            <Card key={metric.label} className="border border-border bg-card">
              <CardContent className="space-y-3 p-4">
                <div className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground">{metric.label}</div>
                <div className="flex items-end justify-between gap-2">
                  <div className="flex items-end gap-2">
                    <span className="text-3xl font-semibold tracking-tight">{metric.after}</span>
                    <span className="pb-1 text-xs text-muted-foreground">{metric.unit}</span>
                  </div>
                  <span className="text-xs text-muted-foreground line-through">{metric.before}</span>
                </div>
                <div className={`flex items-center gap-1.5 text-xs font-medium ${improving ? "text-green-600" : "text-red-500"}`}>
                  {improving ? <TrendingUp className="size-3.5" /> : <TrendingDown className="size-3.5" />}
                  <span>{metric.deltaText}</span>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
      <div className="mt-5 grid grid-cols-12 gap-5">
        <Card className="col-span-12 lg:col-span-7">
          <CardHeader>
            <CardTitle>Before vs After</CardTitle>
            <CardDescription>Before/after comparison in normalized engineering dimensions.</CardDescription>
          </CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData(data)}>
                <CartesianGrid strokeDasharray="2 2" vertical={false} stroke="hsl(var(--border))" />
                <XAxis dataKey="metric" tickLine={false} axisLine={false} tick={{ fontSize: 12 }} />
                <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 12 }} />
                <Tooltip contentStyle={{ borderRadius: 8, borderColor: "hsl(var(--border))" }} />
                <Legend />
                <Bar dataKey="before" name="Before" fill="#9ca3af" radius={[5, 5, 0, 0]} />
                <Bar dataKey="after" name="After" fill="hsl(var(--primary))" radius={[5, 5, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card className="col-span-12 lg:col-span-5">
          <CardHeader>
            <CardTitle>Quality envelope</CardTitle>
            <CardDescription>Six-dimensional quality radar (before vs after).</CardDescription>
          </CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={qualityEnvelopeData(data)}>
                <PolarGrid />
                <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11 }} />
                <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 10 }} />
                <Radar dataKey="before" name="Before" stroke="#9ca3af" fill="#9ca3af" fillOpacity={0.2} />
                <Radar dataKey="after" name="After" stroke="hsl(var(--primary))" fill="hsl(var(--primary))" fillOpacity={0.25} />
                <Tooltip />
                <Legend />
              </RadarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
      <Card className="mt-5">
        <CardHeader><CardTitle>Metric-by-metric</CardTitle></CardHeader>
        <div className="overflow-x-auto">
          <Table>
            <THead><TR><TH>Metric</TH><TH>Before</TH><TH>After</TH><TH>Delta</TH><TH>Direction</TH><TH>Interpretation</TH></TR></THead>
            <TBody>
              {tableRows(data).map((row) => (
                <TR key={row.metric}>
                  <TD className="font-medium">{row.metric}</TD>
                  <TD>{row.before}</TD>
                  <TD>{row.after}</TD>
                  <TD className={row.improved ? "text-green-600" : "text-red-500"}>{row.delta}</TD>
                  <TD>
                    <Badge tone={row.improved ? "success" : "danger"}>{row.improved ? "Improved" : "Regressed"}</Badge>
                  </TD>
                  <TD>{row.interpretation}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </div>
      </Card>
        </>
      ) : null)}
    </>
  );
}

function headlineMetrics(data: MetricsPageData) {
  const report = data.report;
  return [
    {
      label: "LOC",
      before: report.beforeMetrics.loc.toString(),
      after: report.afterMetrics.loc.toString(),
      unit: "lines",
      isImprovement: report.metricsDelta.locDelta <= 0,
      deltaText: formatPercent(report.metricsDelta.locReductionPercent)
    },
    {
      label: "CC",
      before: report.beforeMetrics.cyclomaticComplexity.toString(),
      after: report.afterMetrics.cyclomaticComplexity.toString(),
      unit: "score",
      isImprovement: report.metricsDelta.cyclomaticComplexityDelta <= 0,
      deltaText: formatPercent(report.metricsDelta.complexityReductionPercent)
    },
    {
      label: "MI",
      before: report.beforeMetrics.maintainabilityIndex.toString(),
      after: report.afterMetrics.maintainabilityIndex.toString(),
      unit: "index",
      isImprovement: report.metricsDelta.maintainabilityIndexDelta >= 0,
      deltaText: formatPercent(report.metricsDelta.maintainabilityImprovementPercent)
    },
    {
      label: "SCAN TIME",
      before: report.beforeMetrics.estimatedScanTimeMs.toFixed(2),
      after: report.afterMetrics.estimatedScanTimeMs.toFixed(2),
      unit: "ms",
      isImprovement: report.metricsDelta.estimatedScanTimeDelta <= 0,
      deltaText: formatPercent(report.metricsDelta.scanTimeReductionPercent)
    }
  ];
}

function barData(data: MetricsPageData) {
  const report = data.report;
  return [
    { metric: "LOC", before: report.beforeMetrics.loc, after: report.afterMetrics.loc },
    { metric: "CC", before: report.beforeMetrics.cyclomaticComplexity, after: report.afterMetrics.cyclomaticComplexity },
    { metric: "MI/100", before: round(report.beforeMetrics.maintainabilityIndex / 100), after: round(report.afterMetrics.maintainabilityIndex / 100) },
    {
      metric: "Scan(ms)x10",
      before: round(report.beforeMetrics.estimatedScanTimeMs * 10),
      after: round(report.afterMetrics.estimatedScanTimeMs * 10)
    },
    {
      metric: "VR%",
      before: validationRateValue(report.latestValidationStatus),
      after: validationRateValue(report.latestValidationStatus)
    }
  ];
}

function qualityEnvelopeData(data: MetricsPageData) {
  const report = data.report;
  const maintainabilityBefore = clamp(report.beforeMetrics.maintainabilityIndex);
  const maintainabilityAfter = clamp(report.afterMetrics.maintainabilityIndex);
  const compactnessBefore = clamp(100 - report.beforeMetrics.loc);
  const compactnessAfter = clamp(100 - report.afterMetrics.loc);
  const simplicityBefore = clamp(100 - report.beforeMetrics.cyclomaticComplexity * 10);
  const simplicityAfter = clamp(100 - report.afterMetrics.cyclomaticComplexity * 10);
  const determinismBefore = clamp(100 - report.beforeMetrics.estimatedScanTimeMs * 12);
  const determinismAfter = clamp(100 - report.afterMetrics.estimatedScanTimeMs * 12);
  const readabilityBefore = clamp((maintainabilityBefore + simplicityBefore) / 2);
  const readabilityAfter = clamp((maintainabilityAfter + simplicityAfter) / 2);
  const verifiabilityBefore = validationRateValue(report.latestValidationStatus);
  const verifiabilityAfter = validationRateValue(report.latestValidationStatus);

  return [
    { subject: "Maintainability", before: maintainabilityBefore, after: maintainabilityAfter },
    { subject: "Verifiability", before: verifiabilityBefore, after: verifiabilityAfter },
    { subject: "Compactness", before: compactnessBefore, after: compactnessAfter },
    { subject: "Simplicity", before: simplicityBefore, after: simplicityAfter },
    { subject: "Determinism", before: determinismBefore, after: determinismAfter },
    { subject: "Readability", before: readabilityBefore, after: readabilityAfter }
  ];
}

function tableRows(data: MetricsPageData) {
  const report = data.report;
  return [
    {
      metric: "Lines of Code",
      before: report.beforeMetrics.loc.toString(),
      after: report.afterMetrics.loc.toString(),
      delta: formatSigned(report.metricsDelta.locDelta),
      improved: report.metricsDelta.locDelta <= 0,
      interpretation: "Lower LOC typically indicates tighter implementation with fewer maintenance points."
    },
    {
      metric: "Cyclomatic Complexity",
      before: report.beforeMetrics.cyclomaticComplexity.toString(),
      after: report.afterMetrics.cyclomaticComplexity.toString(),
      delta: formatSigned(report.metricsDelta.cyclomaticComplexityDelta),
      improved: report.metricsDelta.cyclomaticComplexityDelta <= 0,
      interpretation: "Lower branch complexity improves predictability and makes the code easier to review and test."
    },
    {
      metric: "Maintainability Index",
      before: report.beforeMetrics.maintainabilityIndex.toString(),
      after: report.afterMetrics.maintainabilityIndex.toString(),
      delta: formatSigned(report.metricsDelta.maintainabilityIndexDelta),
      improved: report.metricsDelta.maintainabilityIndexDelta >= 0,
      interpretation: "Higher index suggests simpler future updates and lower technical debt risk."
    },
    {
      metric: "Estimated Scan Time",
      before: `${report.beforeMetrics.estimatedScanTimeMs.toFixed(2)} ms`,
      after: `${report.afterMetrics.estimatedScanTimeMs.toFixed(2)} ms`,
      delta: `${formatSigned(round(report.metricsDelta.estimatedScanTimeDelta))} ms`,
      improved: report.metricsDelta.estimatedScanTimeDelta <= 0,
      interpretation: "Lower scan time supports tighter control loops and improved deterministic response."
    }
  ];
}

function formatSigned(value: number) {
  return `${value >= 0 ? "+" : ""}${value}`;
}

function formatPercent(value: number) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function round(value: number) {
  return Math.round(value * 100) / 100;
}

function clamp(value: number) {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function validationRateValue(status: string | null | undefined) {
  return status === "CHECKS_PASSED" ? 100 : 0;
}

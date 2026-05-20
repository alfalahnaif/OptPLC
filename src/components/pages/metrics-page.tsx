"use client";

import Link from "next/link";
import { ArrowRight, Download } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import { MetricCard } from "@/components/common/metric-card";
import { PageStateGate, type PageState } from "@/components/common/page-state";
import { StatusBadge } from "@/components/common/status-badge";
import { PageHeader } from "@/components/layout/page-header";
import { PipelineStrip } from "@/components/layout/pipeline-strip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { ACTIVE_PROJECT_ID, getMetricsPageData, projectPath, useApiResource } from "@/lib/api-client";

export function MetricsPage({ projectId = ACTIVE_PROJECT_ID, state }: { projectId?: string; state?: PageState } = {}) {
  const resource = useApiResource(() => getMetricsPageData(projectId), [projectId]);
  const effectiveState = state ?? resource.state;
  const data = resource.data;
  const stateView =
    effectiveState !== "ready" || !data ? (
      <PageStateGate
        state={effectiveState === "ready" ? "loading" : effectiveState}
        loading={{ title: "Loading metrics comparison", description: "Preparing before and after optimization metrics." }}
        empty={{ title: "No metrics available", description: "Generate optimized code to populate this comparison." }}
        error={{ title: "Metrics unavailable", description: "The mock metrics report could not be rendered." }}
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
            <Button variant="outline"><Download /> Export CSV</Button>
            <Button asChild><Link href={projectPath(projectId, "report")}>Generate report <ArrowRight /></Link></Button>
          </>
        }
      />
      {stateView ?? (data ? (
        <>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
        {data.metricsCards.map((metric) => (
          <MetricCard key={metric.label} label={metric.label} value={`${metric.after}${metric.suffix}`} detail={`before ${metric.before}${metric.suffix}`} delta={metric.delta.startsWith("+") ? metric.delta : undefined} />
        ))}
      </div>
      <div className="mt-5 grid gap-5 xl:grid-cols-[1.1fr_.8fr]">
        <Card>
          <CardHeader>
            <CardTitle>Before vs After</CardTitle>
            <CardDescription>Lower is better for LOC, CC and scan time; higher is better for MI and VR.</CardDescription>
          </CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.comparisonData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
                <XAxis dataKey="metric" tickLine={false} axisLine={false} tick={{ fontSize: 12 }} />
                <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 12 }} />
                <Tooltip contentStyle={{ borderRadius: 8, borderColor: "hsl(var(--border))" }} />
                <Bar dataKey="before" fill="#969ba8" radius={[5, 5, 0, 0]} />
                <Bar dataKey="after" fill="#315fd1" radius={[5, 5, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Quality envelope</CardTitle>
            <CardDescription>Normalized 0-100 quality dimensions.</CardDescription>
          </CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={data.qualityRadar}>
                <PolarGrid />
                <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11 }} />
                <Radar dataKey="before" stroke="#969ba8" fill="#969ba8" fillOpacity={0.18} />
                <Radar dataKey="after" stroke="#315fd1" fill="#315fd1" fillOpacity={0.22} />
                <Tooltip />
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
              {[
                ["Lines of Code", "47 LOC", "33 LOC", "+29.8%", "Source compaction with no loss of semantics."],
                ["Cyclomatic Complexity", "9", "4", "+55.6%", "Fewer branches, easier exhaustive testing."],
                ["Maintainability Index", "68 / 100", "89 / 100", "+30.9%", "Composite of Halstead, V, CC and SLOC."],
                ["Estimated Scan Time", "4.1 ms", "2.4 ms", "+41.5%", "Modeled at 1 ms tick for target runtime."],
                ["Verification Rate", "75%", "100%", "+33.3%", "Formal properties holding on emitted code."]
              ].map(([metric, before, after, delta, interpretation]) => (
                <TR key={metric}>
                  <TD className="font-medium">{metric}</TD>
                  <TD>{before}</TD>
                  <TD>{after}</TD>
                  <TD>{delta}</TD>
                  <TD><StatusBadge status="optimized" label="Improved" /></TD>
                  <TD>{interpretation}</TD>
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

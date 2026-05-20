"use client";

import Link from "next/link";
import { Download, FileText, Printer } from "lucide-react";

import { PageStateGate, type PageState } from "@/components/common/page-state";
import { StatusBadge } from "@/components/common/status-badge";
import { PageHeader } from "@/components/layout/page-header";
import { PipelineStrip } from "@/components/layout/pipeline-strip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ACTIVE_PROJECT_ID, getReportPageData, useApiResource } from "@/lib/api-client";

export function ReportPage({ projectId = ACTIVE_PROJECT_ID, state }: { projectId?: string; state?: PageState } = {}) {
  const resource = useApiResource(() => getReportPageData(projectId), [projectId]);
  const effectiveState = state ?? resource.state;
  const data = resource.data;
  const stateView =
    effectiveState !== "ready" || !data ? (
      <PageStateGate
        state={effectiveState === "ready" ? "loading" : effectiveState}
        loading={{ title: "Loading final report", description: "Preparing engineering summary and validation evidence." }}
        empty={{ title: "No final report", description: "Complete the pipeline to generate a report." }}
        error={{ title: "Final report unavailable", description: "The mock report could not be rendered." }}
      />
    ) : null;

  const currentProject = data?.currentProject;
  const metricsCards = data?.metricsCards;
  const planObject = data?.planObject;
  const requirement = data?.requirement;

  return (
    <>
      <PipelineStrip projectId={projectId} />
      <PageHeader
        title="Final Report"
        description="Exportable engineering summary for review, handoff, and audit records."
        actions={
          <>
            <Button variant="outline"><Printer /> Print</Button>
            <Button><Download /> Export PDF</Button>
          </>
        }
      />
      {stateView ?? (currentProject && metricsCards && planObject && requirement ? <div className="grid gap-5 xl:grid-cols-[1fr_.42fr]">
        <Card>
          <CardHeader className="border-b-4 border-primary">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm text-muted-foreground">PLC Agent Optimizer</div>
                <CardTitle className="mt-2 text-2xl">{currentProject.name}</CardTitle>
              </div>
              <StatusBadge status="optimized" />
            </div>
          </CardHeader>
          <CardContent className="space-y-8 p-8">
            <section>
              <h2 className="mb-3 text-lg font-semibold">Executive summary</h2>
              <p className="text-sm leading-7 text-muted-foreground">
                The agent pipeline generated IEC 61131-3 Structured Text for a three-phase conveyor motor controller,
                resolved one formal safety violation, then applied three conservative optimization passes. The final
                program is syntax-valid, formally verified against all four safety constraints, and reduced from 47 LOC
                to 33 LOC while improving maintainability from 68 to 89.
              </p>
            </section>
            <section>
              <h2 className="mb-3 text-lg font-semibold">Requirement</h2>
              <p className="rounded-md border bg-muted/30 p-4 text-sm leading-7">{requirement.text}</p>
            </section>
            <section>
              <h2 className="mb-3 text-lg font-semibold">Plan object scope</h2>
              <div className="grid gap-3 md:grid-cols-3">
                <Box label="Inputs" value={planObject.inputs.length} />
                <Box label="Outputs" value={planObject.outputs.length} />
                <Box label="Safety constraints" value={planObject.safetyConstraints.length} />
              </div>
            </section>
            <section>
              <h2 className="mb-3 text-lg font-semibold">Verification evidence</h2>
              <div className="grid gap-3 md:grid-cols-2">
                {requirement.constraints.map((constraint, index) => (
                  <div className="rounded-md border bg-muted/20 p-3 text-sm" key={constraint}>
                    <div className="mb-1 font-mono text-xs text-muted-foreground">SC{index + 1}</div>
                    {constraint}
                    <div className="mt-2"><StatusBadge status="passed" /></div>
                  </div>
                ))}
              </div>
            </section>
          </CardContent>
        </Card>
        <div className="space-y-5">
          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2"><FileText className="size-4 text-primary" /> Report metadata</CardTitle></CardHeader>
            <CardContent className="space-y-3 text-sm">
              <Row label="Project ID" value={currentProject.id} />
              <Row label="Generated" value="2026-05-17 09:43 UTC" />
              <Row label="Standard" value={currentProject.standard} />
              <Row label="Runtime" value={currentProject.runtime} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Metric summary</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {metricsCards.slice(0, 4).map((metric) => (
                <div className="flex justify-between rounded-md border bg-muted/30 p-3 text-sm" key={metric.label}>
                  <span>{metric.label}</span>
                  <span className="font-semibold">{metric.after}{metric.suffix}</span>
                </div>
              ))}
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

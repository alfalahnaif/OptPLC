"use client";

import Link from "next/link";
import { ArrowRight, Copy, Download, FileJson, GitBranch } from "lucide-react";

import { PageStateGate, type PageState } from "@/components/common/page-state";
import { PlanningModeBadge } from "@/components/common/planning-mode-badge";
import { StatusBadge } from "@/components/common/status-badge";
import { PageHeader } from "@/components/layout/page-header";
import { PipelineStrip } from "@/components/layout/pipeline-strip";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ACTIVE_PROJECT_ID, generatePlan, projectPath, useApiResource } from "@/lib/api-client";

export function PlanPage({ projectId = ACTIVE_PROJECT_ID, state }: { projectId?: string; state?: PageState } = {}) {
  const resource = useApiResource(() => generatePlan(projectId), [projectId]);
  const effectiveState = state ?? resource.state;
  const planObject = resource.data;
  const stateView =
    effectiveState !== "ready" || !planObject ? (
      <PageStateGate
        state={effectiveState === "ready" ? "loading" : effectiveState}
        loading={{ title: "Loading Plan Object", description: "Preparing canonical I/O, logic, and safety constraints." }}
        empty={{ title: "No Plan Object generated", description: "Generate a plan from requirements to preview this page." }}
        error={{ title: "Plan Object unavailable", description: resource.error?.message ?? "The Plan Object could not be loaded." }}
      />
    ) : null;

  return (
    <>
      <PipelineStrip projectId={projectId} />
      <PageHeader
        eyebrow="Pipeline - Step 3 of 9"
        title="Plan Object preview"
        description="Canonical Plan Object emitted by the Planning Agent. Review I/O, control logic and safety constraints before generating ST code."
        actions={
          <>
            <PlanningModeBadge />
            <StatusBadge status="completed" label="Planning Agent - Completed" />
            <Button variant="outline" asChild><Link href={projectPath(projectId, "requirements")}>Edit Requirements</Link></Button>
            <Button asChild><Link href={projectPath(projectId, "code")}>Generate Code <ArrowRight /></Link></Button>
          </>
        }
      />
      {stateView ?? (planObject ? (
        <>
      <Card className="mb-5">
        <CardContent className="grid gap-4 p-5 md:grid-cols-5">
          {[
            ["Project", planObject.projectId],
            ["Agent", planObject.agent],
            ["Inputs", planObject.inputs.length],
            ["Outputs", planObject.outputs.length],
            ["Safety SC", planObject.safetyConstraints.length]
          ].map(([label, value]) => (
            <div key={label}>
              <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</div>
              <div className="mt-2 text-lg font-semibold">{value}</div>
            </div>
          ))}
        </CardContent>
      </Card>

      <div className="grid gap-5 xl:grid-cols-[1.1fr_.9fr]">
        <div className="space-y-5">
          <div className="grid gap-5 md:grid-cols-2">
            <SignalCard title="Inputs" items={planObject.inputs.map((item) => ({ ...item, source: item.source ?? item.address ?? "-" }))} />
            <SignalCard title="Outputs" items={planObject.outputs.map((o) => ({ ...o, source: o.address ?? o.source ?? "-" }))} />
          </div>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><GitBranch className="size-4 text-primary" /> Control logic - {planObject.logicRules.length} rules</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {planObject.logicRules.map((rule, index) => (
                <div className="flex gap-3 rounded-md border bg-muted/25 p-3 text-sm" key={rule}>
                  <span className="font-mono text-xs text-muted-foreground">L{index + 1}</span>
                  <span>{rule}</span>
                </div>
              ))}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Safety constraints - {planObject.safetyConstraints.length}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {planObject.safetyConstraints.map((rule, index) => (
                <div className="flex items-center justify-between rounded-md border bg-muted/25 p-3 text-sm" key={rule}>
                  <span><span className="mr-2 font-mono text-xs text-muted-foreground">SC{index + 1}</span>{rule}</span>
                  <Badge tone={index < 2 ? "danger" : "warning"}>{index < 2 ? "Critical" : "High"}</Badge>
                </div>
              ))}
            </CardContent>
          </Card>
          <div className="grid gap-5 md:grid-cols-2">
            <Card>
              <CardHeader><CardTitle>Performance targets</CardTitle></CardHeader>
              <CardContent className="space-y-2 text-sm">
                <Row label="Max scan time" value="5 ms" />
                <Row label="Max CC" value="8" />
                <Row label="Min MI" value="75" />
                <Row label="Max LOC" value="120" />
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>IEC scope</CardTitle></CardHeader>
              <CardContent className="space-y-2 text-sm">
                {Object.entries(planObject.scope).map(([label, value]) => (
                  <Row key={label} label={label} value={value} />
                ))}
              </CardContent>
            </Card>
          </div>
        </div>

        <Card className="h-fit">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2"><FileJson className="size-4 text-primary" /> plan_object.json</CardTitle>
              <CardDescription>Canonical machine-readable form passed to the Code Generation Agent.</CardDescription>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm"><Copy /> Copy</Button>
              <Button variant="outline" size="sm"><Download /> Download</Button>
            </div>
          </CardHeader>
          <CardContent>
            <pre className="max-h-[720px] overflow-auto rounded-md bg-muted p-4 font-mono text-xs leading-6">
              {JSON.stringify(planObject, null, 2)}
            </pre>
          </CardContent>
        </Card>
      </div>
        </>
      ) : null)}
    </>
  );
}

function SignalCard({ title, items }: { title: string; items: { name: string; type: string; source: string; description: string }[] }) {
  return (
    <Card>
      <CardHeader><CardTitle>{title} - {items.length}</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        {items.map((item) => (
          <div className="rounded-md border bg-muted/25 p-3" key={item.name}>
            <div className="flex items-center justify-between">
              <div className="font-mono text-sm font-semibold">{item.name} <Badge tone="info" className="font-mono">{item.type}</Badge></div>
              <div className="font-mono text-xs text-muted-foreground">{item.source}</div>
            </div>
            <div className="mt-1 text-xs text-muted-foreground">{item.description}</div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function Row({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="capitalize text-muted-foreground">{label}</span>
      <span className="text-right font-medium">{value}</span>
    </div>
  );
}

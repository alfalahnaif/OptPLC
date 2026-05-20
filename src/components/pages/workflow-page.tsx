"use client";

import Link from "next/link";
import { ArrowRight, RotateCcw } from "lucide-react";

import { PageStateGate, type PageState } from "@/components/common/page-state";
import { RepairLoopPanel } from "@/components/common/repair-loop-panel";
import { StatusBadge } from "@/components/common/status-badge";
import { PageHeader } from "@/components/layout/page-header";
import { PipelineStrip } from "@/components/layout/pipeline-strip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ACTIVE_PROJECT_ID, getWorkflowMonitorData, projectPath, useApiResource } from "@/lib/api-client";
import { cn } from "@/lib/utils";

export function WorkflowPage({ projectId = ACTIVE_PROJECT_ID, state }: { projectId?: string; state?: PageState } = {}) {
  const resource = useApiResource(() => getWorkflowMonitorData(projectId), [projectId]);
  const effectiveState = state ?? resource.state;
  const data = resource.data;
  const stateView =
    effectiveState !== "ready" || !data ? (
      <PageStateGate
        state={effectiveState === "ready" ? "loading" : effectiveState}
        loading={{ title: "Loading agent workflow", description: "Preparing mocked agent events and session logs." }}
        empty={{ title: "No workflow events", description: "Start generation to populate the agent monitor." }}
        error={{ title: "Workflow unavailable", description: "The mock workflow session could not be rendered." }}
      />
    ) : null;

  return (
    <>
      <PipelineStrip projectId={projectId} />
      <PageHeader
        eyebrow="Pipeline - Step 4 of 9"
        title="Agent workflow monitor"
        description="Live view of the five-agent pipeline. One validation failure occurred on iteration 1 and was resolved on iteration 2."
        actions={
          <>
            <StatusBadge status="completed" label="Completed" />
            <Button variant="outline"><RotateCcw /> Replay session</Button>
            <Button asChild><Link href={projectPath(projectId, "code")}>View generated code <ArrowRight /></Link></Button>
          </>
        }
      />
      {stateView ?? (data ? (
        <>
      <Card className="mb-5">
        <CardContent className="grid gap-4 p-5 md:grid-cols-5">
          {["Planning", "Code Gen", "Validation", "Debugging", "Optimization"].map((step, index) => (
            <div className="flex items-center justify-center gap-4" key={step}>
              <div className="text-center">
                <span className="mx-auto grid size-8 place-items-center rounded-full border border-emerald-600 text-emerald-700">
                  {index + 1}
                </span>
                <div className="mt-2 text-sm font-medium">{step}</div>
                <div className="font-mono text-xs text-muted-foreground">{index + 1} / 5</div>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
      <div className="grid gap-5 xl:grid-cols-[1.4fr_.7fr]">
        <div className="space-y-4">
          {data.workflowEvents.map((event) => {
            const Icon = event.icon;
            const failed = event.status === "failed";
            return (
              <Card key={`${event.agent}-${event.iter}-${event.output}`} className={cn(failed && "border-red-200 bg-red-50/30 dark:border-red-900 dark:bg-red-950/10")}>
                <CardContent className="grid gap-4 p-4 md:grid-cols-[44px_1fr_1fr_64px] md:items-center">
                  <span className={cn("grid size-10 place-items-center rounded-md border bg-muted", failed && "border-red-300 text-red-700")}>
                    <Icon className="size-4" />
                  </span>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold">{event.agent}</span>
                      <StatusBadge status={failed ? "failed" : "completed"} />
                    </div>
                    <div className="mt-2 text-xs uppercase tracking-wider text-muted-foreground">Input</div>
                    <div className="text-sm text-muted-foreground">{event.input}</div>
                  </div>
                  <div>
                    <div className="text-xs uppercase tracking-wider text-muted-foreground">Output</div>
                    <div className="text-sm text-muted-foreground">{event.output}</div>
                  </div>
                  <div className="font-mono text-xs text-muted-foreground">{event.duration}</div>
                </CardContent>
              </Card>
            );
          })}
        </div>
        <Card className="h-fit">
          <CardHeader>
            <CardTitle>Session log</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="max-h-[620px] overflow-auto rounded-md bg-muted p-3 font-mono text-xs">
              {data.sessionLog.map(([time, level, scope, message]) => (
                <div className="grid grid-cols-[64px_52px_78px_1fr] gap-2 border-b py-2 last:border-0" key={`${time}-${message}`}>
                  <span className="text-muted-foreground">{time}</span>
                  <span>{level}</span>
                  <span className="text-muted-foreground">{scope}</span>
                  <span>{message}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
      {data.repairLoopReport ? <RepairLoopPanel report={data.repairLoopReport} /> : null}
        </>
      ) : null)}
    </>
  );
}

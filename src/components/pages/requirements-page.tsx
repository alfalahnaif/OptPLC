"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowRight, FileText, Loader2, Plus, ShieldCheck } from "lucide-react";

import { PageStateGate, type PageState } from "@/components/common/page-state";
import { PlanningModeBadge } from "@/components/common/planning-mode-badge";
import { PageHeader } from "@/components/layout/page-header";
import { PipelineStrip } from "@/components/layout/pipeline-strip";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import {
  ACTIVE_PROJECT_ID,
  getRequirementPageData,
  isMockApiEnabled,
  projectPath,
  submitRequirements,
  useApiResource
} from "@/lib/api-client";

export function RequirementsPage({ projectId = ACTIVE_PROJECT_ID, state }: { projectId?: string; state?: PageState } = {}) {
  const router = useRouter();
  const mockMode = isMockApiEnabled();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const resource = useApiResource(() => getRequirementPageData(projectId), [projectId]);
  const effectiveState = state ?? resource.state;
  const data = resource.data;
  const stateView =
    effectiveState !== "ready" || !data ? (
      <PageStateGate
        state={effectiveState === "ready" ? "loading" : effectiveState}
        loading={{ title: "Loading requirement input", description: "Preparing mock requirement text and derived I/O." }}
        empty={{ title: "No requirement text", description: "Enter a control requirement to generate a Plan Object." }}
        error={{ title: "Requirement preview unavailable", description: "The mock requirement data could not be parsed." }}
      />
    ) : null;

  const requirement = data?.requirement;
  const planObject = data?.derivedPlan;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mockMode || !requirement) return;

    const formData = new FormData(event.currentTarget);
    const extraConstraint = String(formData.get("newSafetyConstraint") ?? "").trim();
    const safetyConstraints = [
      ...requirement.constraints,
      ...(extraConstraint ? [extraConstraint] : [])
    ];

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      await submitRequirements({
        projectId,
        text: String(formData.get("requirementText") ?? ""),
        safetyConstraints,
        performanceTargets: {
          maxScanTimeMs: requirement.performanceTargets.scanTimeMs,
          maxCyclomaticComplexity: requirement.performanceTargets.cyclomaticComplexity,
          minMaintainabilityIndex: requirement.performanceTargets.maintainability,
          maxIterations: requirement.performanceTargets.maxIterations
        }
      });
      router.push(projectPath(projectId, "plan"));
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "Unable to submit requirements.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <>
      <PipelineStrip projectId={projectId} />
      <PageHeader
        eyebrow="Pipeline - Step 2 of 9"
        title="Requirement Input"
        description="Describe the control behavior in plain industrial English. The Planning Agent extracts I/O, control rules and safety constraints into a Plan Object."
        actions={<PlanningModeBadge />}
      />
      {stateView ?? (requirement && planObject ? <form onSubmit={handleSubmit} className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <div className="space-y-5">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="size-4 text-primary" />
                  Control requirement
                </CardTitle>
                <CardDescription>Plain-English description with pre-conditions, fault behavior, and operator actions.</CardDescription>
              </div>
              <div className="font-mono text-xs text-muted-foreground">472 chars - 74 words</div>
            </CardHeader>
            <CardContent>
              <Textarea name="requirementText" className="min-h-56" defaultValue={requirement.text} />
              <div className="mt-4 flex flex-wrap gap-2">
                {["Motor start/stop with emergency stop", "Traffic light controller", "Tank level control", "Sequential batch process"].map((item) => (
                  <Button key={item} variant="outline" size="sm">{item}</Button>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ShieldCheck className="size-4 text-warning" />
                Safety constraints
              </CardTitle>
              <CardDescription>Asserted properties the Validation Agent will formally check.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {requirement.constraints.map((constraint, index) => (
                <div className="flex items-center justify-between rounded-md border bg-muted/30 p-3 text-sm" key={constraint}>
                  <span>{constraint}</span>
                  <span className="font-mono text-xs text-muted-foreground">SC{index + 1}</span>
                </div>
              ))}
              <div className="flex gap-2">
                <Input name="newSafetyConstraint" placeholder="Add a safety property" />
                <Button type="button" variant="outline"><Plus /> Add</Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Performance targets</CardTitle>
              <CardDescription>The Optimization Agent iterates until targets are met or all passes are exhausted.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-6 md:grid-cols-3">
              <div>
                <div className="mb-2 text-sm font-medium">Max scan time</div>
                <Progress value={55} />
                <div className="mt-2 text-xs text-muted-foreground">{requirement.performanceTargets.scanTimeMs} ms</div>
              </div>
              <div>
                <div className="mb-2 text-sm font-medium">Max cyclomatic CC</div>
                <Progress value={62} />
                <div className="mt-2 text-xs text-muted-foreground">{requirement.performanceTargets.cyclomaticComplexity}</div>
              </div>
              <div>
                <div className="mb-2 text-sm font-medium">Min maintainability</div>
                <Progress value={75} />
                <div className="mt-2 text-xs text-muted-foreground">{requirement.performanceTargets.maintainability} / 100</div>
              </div>
              {submitError ? (
                <div className="md:col-span-3">
                  <Alert variant="destructive">
                    <AlertTitle>Requirement submission failed</AlertTitle>
                    <AlertDescription>{submitError}</AlertDescription>
                  </Alert>
                </div>
              ) : null}
              <div className="md:col-span-3 flex justify-end border-t pt-4">
                {mockMode ? <Button asChild>
                  <Link href={projectPath(projectId, "plan")}>
                    Generate Plan Object
                    <ArrowRight />
                  </Link>
                </Button> : (
                  <Button type="submit" disabled={isSubmitting}>
                    {isSubmitting ? <Loader2 className="animate-spin" /> : null}
                    Generate Plan Object
                    <ArrowRight />
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        <Card className="h-fit">
          <CardHeader>
            <CardTitle>Live preview - derived Plan</CardTitle>
            <CardDescription>Best-effort parse before the canonical Plan Object is generated.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-md border bg-muted/40 p-3">
                <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Detected domain</div>
                <div className="mt-1 font-medium">Safety Interlocks</div>
              </div>
              <div className="rounded-md border bg-muted/40 p-3">
                <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Heuristic confidence</div>
                <div className="mt-1 font-medium">High - 0.92</div>
              </div>
            </div>
            <SignalList title="Inferred inputs" items={planObject.inputs} tag="IN" />
            <SignalList title="Inferred outputs" items={planObject.outputs} tag="OUT" />
            <div>
              <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Safety constraints</div>
              <div className="space-y-2 text-sm">
                {requirement.constraints.slice(0, 3).map((constraint, index) => (
                  <div key={constraint}><span className="mr-2 font-mono text-xs text-muted-foreground">SC{index + 1}</span>{constraint}</div>
                ))}
              </div>
            </div>
            <div className="rounded-md border border-sky-200 bg-sky-50 p-3 text-sm text-sky-800 dark:border-sky-900 dark:bg-sky-950/30 dark:text-sky-300">
              Continue to generate the canonical Plan Object, including I/O wiring, control logic, and IEC scope.
            </div>
          </CardContent>
        </Card>
      </form> : null)}
    </>
  );
}

function SignalList({
  title,
  items,
  tag
}: {
  title: string;
  items: { name: string; type: string }[];
  tag: string;
}) {
  return (
    <div>
      <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        {title} - {items.length}
      </div>
      <div className="space-y-2">
        {items.map((item) => (
          <div className="rounded-md bg-muted px-3 py-2 font-mono text-xs" key={item.name}>
            <Badge tone={tag === "IN" ? "info" : "primary"} className="mr-2 font-mono">{tag}</Badge>
            {item.name} <span className="text-muted-foreground">: {item.type}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

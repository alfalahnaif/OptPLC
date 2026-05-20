"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowRight, Box, FileCode2, Folder, Info, Loader2, Network, ShieldCheck } from "lucide-react";

import { PageStateGate, type PageState } from "@/components/common/page-state";
import { PageHeader } from "@/components/layout/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ACTIVE_PROJECT_ID, createProject, isMockApiEnabled, projectPath } from "@/lib/api-client";

const domains = ["Traffic Control", "Motor Control", "Process Control", "Safety Interlocks", "Sequential Batch"];
const complexityTiers = [
  ["simple", "Simple", "< 5 I/O - 1 state machine"],
  ["medium", "Medium", "5-20 I/O - interlocks - safety"],
  ["complex", "Complex", "> 20 I/O - sequences - multi-mode"]
] as const;

export function NewProjectPage({ state = "ready" }: { state?: PageState } = {}) {
  const router = useRouter();
  const mockMode = isMockApiEnabled();
  const [selectedDomain, setSelectedDomain] = useState("Motor Control");
  const [complexityTier, setComplexityTier] = useState<"simple" | "medium" | "complex">("medium");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mockMode) return;

    const formData = new FormData(event.currentTarget);
    setIsSubmitting(true);
    setSubmitError(null);

    try {
      const project = await createProject({
        name: String(formData.get("name") ?? ""),
        description: String(formData.get("description") ?? ""),
        domain: selectedDomain,
        targetLanguage: "Structured Text",
        complexityTier
      });
      router.push(projectPath(project.id, "requirements"));
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "Unable to create project.");
    } finally {
      setIsSubmitting(false);
    }
  }

  const stateView =
    state !== "ready" ? (
      <PageStateGate
        state={state}
        loading={{ title: "Loading project form", description: "Preparing mock defaults and engineering metadata." }}
        empty={{ title: "No project template", description: "The new project form is ready for a backend template source." }}
        error={{ title: "Project form unavailable", description: "The mock project template could not be rendered." }}
      />
    ) : null;

  if (stateView) {
    return (
      <>
        <PageHeader
          eyebrow="Pipeline - Step 1 of 9"
          title="Create new PLC project"
          description="Define the engineering envelope. The Planning Agent will use these fields to scope the Plan Object."
        />
        {stateView}
      </>
    );
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[2fr_1fr]">
      <div>
        <PageHeader
          eyebrow="Pipeline - Step 1 of 9"
          title="Create new PLC project"
          description="Define the engineering envelope. The Planning Agent will use these fields to scope the Plan Object."
        />
        <form onSubmit={handleSubmit}>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Folder className="size-4 text-primary" />
              Project information
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div>
              <label className="text-sm font-medium" htmlFor="project-name">Project name</label>
              <Input id="project-name" name="name" className="mt-2" defaultValue="Motor Control - Conveyor M-12" />
            </div>
            <div>
              <label className="text-sm font-medium" htmlFor="project-description">Description</label>
              <Textarea
                id="project-description"
                name="description"
                className="mt-2 min-h-24"
                defaultValue="Three-phase motor on conveyor M-12 with start/stop, E-stop and overload protection. Operator must explicitly reset after a fault before motor will restart."
              />
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="text-sm font-medium">Target language</label>
                <Select defaultValue="st">
                  <SelectTrigger className="mt-2">
                    <SelectValue placeholder="Select language" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="st">Structured Text (ST)</SelectItem>
                  </SelectContent>
                </Select>
                <p className="mt-2 text-xs text-muted-foreground">ST is recommended for verifiable, maintainable code.</p>
              </div>
              <div>
                <label className="text-sm font-medium">IEC standard</label>
                <div className="mt-2 flex h-9 items-center rounded-md border bg-muted/40 px-3 text-sm text-muted-foreground">
                  IEC 61131-3
                </div>
                <p className="mt-2 text-xs text-muted-foreground">Locked to IEC 61131-3 3rd ed. for this release.</p>
              </div>
            </div>
            <div>
              <label className="text-sm font-medium">Project domain</label>
              <div className="mt-2 grid gap-2 md:grid-cols-5">
                {domains.map((domain) => (
                  <button
                    key={domain}
                    type="button"
                    onClick={() => setSelectedDomain(domain)}
                    className={`rounded-md border px-3 py-3 text-left text-sm font-medium ${domain === selectedDomain ? "border-primary bg-primary/5 text-primary" : "bg-card hover:bg-muted"}`}
                  >
                    <Box className="mb-2 size-4" />
                    {domain}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-sm font-medium">Complexity tier</label>
              <div className="mt-2 grid gap-2 md:grid-cols-3">
                {complexityTiers.map(([value, tier, detail]) => (
                  <button
                    key={tier}
                    type="button"
                    onClick={() => setComplexityTier(value)}
                    className={`rounded-md border p-4 text-left ${value === complexityTier ? "border-primary bg-primary/5" : "bg-card hover:bg-muted"}`}
                  >
                    <div className="font-semibold">{tier}</div>
                    <div className="mt-1 text-xs text-muted-foreground">{detail}</div>
                  </button>
                ))}
              </div>
            </div>
            {submitError ? (
              <Alert variant="destructive">
                <AlertTitle>Project creation failed</AlertTitle>
                <AlertDescription>{submitError}</AlertDescription>
              </Alert>
            ) : null}
            <div className="flex items-center justify-between border-t pt-5">
              <Button variant="ghost">Cancel</Button>
              {mockMode ? <Button asChild>
                <Link href={projectPath(ACTIVE_PROJECT_ID, "requirements")}>
                  Continue to Requirements
                  <ArrowRight />
                </Link>
              </Button> : (
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting ? <Loader2 className="animate-spin" /> : null}
                  Continue to Requirements
                  <ArrowRight />
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
        </form>
      </div>

      <div className="space-y-5">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Info className="size-4 text-primary" />
              About Structured Text
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <p>
              Structured Text is a Pascal-like textual language standardized by IEC 61131-3. Typed variables,
              explicit control flow, and POU boundaries make it a natural target for LLM generation and static analysis.
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>What the pipeline does</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {[
              ["Planning Agent", "Parses requirement into I/O, logic, and safety"],
              ["Code Generation Agent", "Synthesizes ST from Plan Object and RAG context"],
              ["Validation Agent", "Runs MATIEC syntax plus nuXmv formal checks"],
              ["Debugging Agent", "Analyzes counterexamples and drafts patch advice"],
              ["Optimization Agent", "Applies conservative simplification with revalidation"]
            ].map(([name, detail], index) => (
              <div className="flex gap-3 rounded-md border bg-muted/30 p-3" key={name}>
                <span className="grid size-6 shrink-0 place-items-center rounded-md bg-card text-xs font-semibold">{index + 1}</span>
                <div>
                  <div className="text-sm font-medium">{name}</div>
                  <div className="text-xs text-muted-foreground">{detail}</div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Expected outputs</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex items-center gap-2"><FileCode2 className="size-4 text-muted-foreground" /> IEC 61131-3 ST source (.st)</div>
            <div className="flex items-center gap-2"><ShieldCheck className="size-4 text-muted-foreground" /> Validation report</div>
            <div className="flex items-center gap-2"><Network className="size-4 text-muted-foreground" /> Optimization metrics</div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

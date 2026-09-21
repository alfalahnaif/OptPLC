"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type ReactNode, useState } from "react";
import { ArrowRight, FileText, Loader2, Pencil, Plus, ShieldCheck, X } from "lucide-react";

import { PageStateGate, type PageState } from "@/components/common/page-state";
import { PlanningModeBadge } from "@/components/common/planning-mode-badge";
import { PageHeader } from "@/components/layout/page-header";
import { PipelineStrip } from "@/components/layout/pipeline-strip";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  ACTIVE_PROJECT_ID,
  analyzeRequirement,
  createPlan,
  getRequirementPageData,
  isMockApiEnabled,
  projectPath,
  submitRequirements,
  useApiResource
} from "@/lib/api-client";
import type { AnalysisResult } from "@/lib/api-contracts";
import { deriveRequirementAnalysisPreview } from "@/lib/requirement-analysis";

type RequirementPageData = Awaited<ReturnType<typeof getRequirementPageData>>;

export function RequirementsPage({ projectId = ACTIVE_PROJECT_ID, state }: { projectId?: string; state?: PageState } = {}) {
  // The loaded data carries its project id, so a project switch never shows the previous project's data.
  const resource = useApiResource(async () => ({ projectId, page: await getRequirementPageData(projectId) }), [projectId]);
  const effectiveState = state ?? resource.state;
  const data = resource.data?.projectId === projectId ? resource.data.page : null;
  const stateView =
    effectiveState !== "ready" || !data ? (
      <PageStateGate
        state={effectiveState === "ready" ? "loading" : effectiveState}
        loading={{ title: "Loading requirement input", description: "Loading persisted requirement payload for this project." }}
        empty={{ title: "No requirement text", description: "Enter a control requirement to generate a Plan Object." }}
        error={{ title: "Requirement preview unavailable", description: "Persisted requirement data could not be loaded." }}
      />
    ) : null;

  return (
    <>
      <PipelineStrip projectId={projectId} />
      <PageHeader
        eyebrow="Pipeline - Step 2 of 9"
        title="Requirement Input"
        description="Describe the control behavior in plain industrial English. The Planning Agent extracts I/O, control rules and safety constraints into a Plan Object."
        actions={<PlanningModeBadge />}
      />
      {stateView ?? (data ? <RequirementsForm key={projectId} projectId={projectId} data={data} /> : null)}
    </>
  );
}

// Created only once the data has loaded, so the form state starts from it without a load effect.
// A load effect could run after the first keystroke and overwrite the typed text (P1-25, D-034).
function RequirementsForm({ projectId, data }: { projectId: string; data: RequirementPageData }) {
  const router = useRouter();
  const mockMode = isMockApiEnabled();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [controlRequirementText, setControlRequirementText] = useState(data.requirementText);
  const [confirmedSafetyConstraints, setConfirmedSafetyConstraints] = useState<string[]>(data.userSafetyConstraints);
  const [newSafetyConstraint, setNewSafetyConstraint] = useState("");
  const [performanceTargets, setPerformanceTargets] = useState(data.performanceTargets);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [hasAnalyzedRequirement, setHasAnalyzedRequirement] = useState(false);
  const [analysisPreview, setAnalysisPreview] = useState<AnalysisResult | null>(null);
  const [confirmedInputs, setConfirmedInputs] = useState<string[]>(data.confirmedInputs);
  const [confirmedOutputs, setConfirmedOutputs] = useState<string[]>(data.confirmedOutputs);
  const [dismissedSuggestedOutputs, setDismissedSuggestedOutputs] = useState<string[]>([]);
  const [suggestedSafetyConstraints, setSuggestedSafetyConstraints] = useState<string[]>([]);
  const [inferredInputs, setInferredInputs] = useState<EditableSignal[]>([]);
  const [suggestedOutputs, setSuggestedOutputs] = useState<EditableSignal[]>([]);
  const [suggestedInternals, setSuggestedInternals] = useState<EditableSignal[]>([]);
  const [newInputDraft, setNewInputDraft] = useState<EditableSignal>({ name: "", type: "BOOL", source: "Operator", description: "" });
  const [newOutputDraft, setNewOutputDraft] = useState<EditableSignal>({ name: "", type: "BOOL", source: "Operator", description: "" });

  const visibleSuggestedOutputs = suggestedOutputs.filter(
    (item) => !confirmedOutputs.includes(item.name) && !dismissedSuggestedOutputs.includes(item.name)
  );
  const confirmedOutputSignals = suggestedOutputs.filter((item) => confirmedOutputs.includes(item.name));
  const hasRequirementText = controlRequirementText.trim().length > 0;
  const shouldShowAnalyzedPreview = hasRequirementText && hasAnalyzedRequirement && analysisPreview !== null;

  function resetAnalysisState() {
    setAnalyzeError(null);
    setIsAnalyzing(false);
    setHasAnalyzedRequirement(false);
    setAnalysisPreview(null);
    setDismissedSuggestedOutputs([]);
    setSuggestedSafetyConstraints([]);
    setConfirmedInputs([]);
    setConfirmedOutputs([]);
    setInferredInputs([]);
    setSuggestedOutputs([]);
    setSuggestedInternals([]);
    setNewInputDraft({ name: "", type: "BOOL", source: "Operator", description: "" });
    setNewOutputDraft({ name: "", type: "BOOL", source: "Operator", description: "" });
  }

  function syncConfirmedInputs(signals: EditableSignal[]) {
    setConfirmedInputs(signals.map((item) => item.name.trim()).filter((item) => item.length > 0));
  }

  function normalizeSignalName(value: string) {
    return value.trim().replace(/\s+/g, "_");
  }

  function applyAnalysisResult(result: AnalysisResult) {
    const inputSignals = dedupeSignals(
      (result.inferred_inputs ?? []).map((item) => ({
        name: item.name,
        type: item.type,
        source: item.source,
        description: item.description
      }))
    );
    const outputSignals = dedupeSignals(
      (result.suggested_outputs ?? []).map((item) => ({
        name: item.name,
        type: item.type,
        source: item.source,
        description: item.description
      }))
    );
    const internalSignals = dedupeSignals(
      (result.suggested_internals ?? []).map((item) => ({
        name: item.name,
        type: item.type,
        source: item.source,
        description: item.description
      }))
    );
    setAnalysisPreview(result);
    setHasAnalyzedRequirement(true);
    setAnalyzeError(null);
    setDismissedSuggestedOutputs([]);
    setSuggestedSafetyConstraints(result.suggested_constraints ?? []);
    setInferredInputs(inputSignals);
    setSuggestedOutputs(outputSignals);
    setSuggestedInternals(internalSignals);
    syncConfirmedInputs(inputSignals);
    setConfirmedOutputs([]);
  }

  async function handleAnalyzeRequirement() {
    const text = controlRequirementText.trim();
    if (!text) {
      setAnalyzeError("Enter a control requirement first.");
      return;
    }
    setIsAnalyzing(true);
    setAnalyzeError(null);
    try {
      const result = await analyzeRequirement(projectId, text, confirmedSafetyConstraints);
      applyAnalysisResult(result);
    } catch (error) {
      const fallback = deriveRequirementAnalysisPreview({
        projectDomain: data.projectDomain,
        requirementText: text,
        safetyConstraints: confirmedSafetyConstraints
      });
      applyAnalysisResult(fallback);
      setAnalyzeError("LLM analysis unavailable, showing heuristic fallback.");
      if (process.env.NODE_ENV !== "production") {
        console.error("Analysis error:", error);
      }
    } finally {
      setIsAnalyzing(false);
    }
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mockMode) return;
    const text = controlRequirementText.trim();
    if (!text) {
      setSubmitError("Requirement text must not be empty.");
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      const payload = {
        projectId,
        text,
        safetyConstraints: confirmedSafetyConstraints,
        performanceTargets,
        confirmedInputs,
        confirmedOutputs,
        domain: data.projectDomain || undefined,
        complexityTier: data.projectComplexityTier || undefined
      };
      if (process.env.NODE_ENV !== "production") {
        console.debug("[requirements-submit]", {
          textLength: text.length,
          safetyConstraintsCount: payload.safetyConstraints.length,
          confirmedOutputsCount: payload.confirmedOutputs.length,
          performanceTargets: payload.performanceTargets
        });
      }
      await submitRequirements(payload);
      await createPlan(projectId);
      router.push(projectPath(projectId, "plan"));
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "Unable to submit requirements.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
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
            <div className="font-mono text-xs text-muted-foreground">{controlRequirementText.length} chars</div>
          </CardHeader>
          <CardContent>
            <Textarea
              name="requirementText"
              aria-label="Requirement text"
              className="min-h-56"
              value={controlRequirementText}
              onChange={(event) => {
                setControlRequirementText(event.target.value);
                resetAnalysisState();
              }}
            />
            <div className="mt-4 space-y-2">
              <Button type="button" variant="outline" onClick={handleAnalyzeRequirement} disabled={isAnalyzing}>
                {isAnalyzing ? <Loader2 className="animate-spin" /> : null}
                Analyze Requirement
              </Button>
              {analyzeError ? <div className="text-sm text-destructive">{analyzeError}</div> : null}
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {["Motor start/stop with emergency stop", "Traffic light controller", "Tank level control", "Sequential batch process"].map((item) => (
                <Button
                  key={item}
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setControlRequirementText(item);
                    resetAnalysisState();
                  }}
                >
                  {item}
                </Button>
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
            {confirmedSafetyConstraints.length === 0 ? (
              <div className="rounded-md border bg-muted/20 p-3 text-sm text-muted-foreground">
                No confirmed safety constraints yet.
              </div>
            ) : null}
            {confirmedSafetyConstraints.map((constraint, index) => (
              <div className="flex items-center justify-between rounded-md border bg-muted/30 p-3 text-sm" key={constraint}>
                <span>{constraint}</span>
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs text-muted-foreground">SC{index + 1}</span>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setConfirmedSafetyConstraints((prev) => prev.filter((item) => item !== constraint));
                    }}
                  >
                    Remove
                  </Button>
                </div>
              </div>
            ))}
            {suggestedSafetyConstraints.length > 0 ? (
              <div className="rounded-md border bg-muted/20 p-3 text-sm">
                <div className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">Suggested constraints</div>
                <div className="space-y-2">
                  {suggestedSafetyConstraints.map((constraint) => (
                    <div className="flex items-center justify-between gap-2" key={constraint}>
                      <span>{constraint}</span>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setConfirmedSafetyConstraints((prev) => (prev.includes(constraint) ? prev : [...prev, constraint]));
                          setSuggestedSafetyConstraints((prev) => prev.filter((item) => item !== constraint));
                        }}
                      >
                        Accept
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
            <div className="flex gap-2">
              <Input
                name="newSafetyConstraint"
                placeholder="Add a safety property"
                value={newSafetyConstraint}
                onChange={(event) => setNewSafetyConstraint(event.target.value)}
              />
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  const constraint = newSafetyConstraint.trim();
                  if (!constraint) return;
                  setConfirmedSafetyConstraints((prev) => (prev.includes(constraint) ? prev : [...prev, constraint]));
                  setNewSafetyConstraint("");
                }}
              >
                <Plus /> Add
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Performance targets</CardTitle>
            <CardDescription>The Optimization Agent iterates until targets are met or all passes are exhausted.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-6 md:grid-cols-2">
            <div>
              <div className="mb-2 text-sm font-medium">Max scan time</div>
              <Input
                type="range"
                aria-label="Max scan time"
                min={1}
                max={20}
                value={performanceTargets.maxScanTimeMs}
                onChange={(event) => {
                  setPerformanceTargets((prev) => ({ ...prev, maxScanTimeMs: Number(event.target.value) }));
                }}
              />
              <div className="mt-2 text-xs text-muted-foreground">{performanceTargets.maxScanTimeMs} ms</div>
            </div>
            <div>
              <div className="mb-2 text-sm font-medium">Max cyclomatic CC</div>
              <Input
                type="range"
                aria-label="Max cyclomatic complexity"
                min={1}
                max={20}
                value={performanceTargets.maxCyclomaticComplexity}
                onChange={(event) => {
                  setPerformanceTargets((prev) => ({ ...prev, maxCyclomaticComplexity: Number(event.target.value) }));
                }}
              />
              <div className="mt-2 text-xs text-muted-foreground">{performanceTargets.maxCyclomaticComplexity}</div>
            </div>
            <div>
              <div className="mb-2 text-sm font-medium">Min maintainability</div>
              <Input
                type="range"
                aria-label="Min maintainability index"
                min={1}
                max={100}
                value={performanceTargets.minMaintainabilityIndex}
                onChange={(event) => {
                  setPerformanceTargets((prev) => ({ ...prev, minMaintainabilityIndex: Number(event.target.value) }));
                }}
              />
              <div className="mt-2 text-xs text-muted-foreground">{performanceTargets.minMaintainabilityIndex} / 100</div>
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
          <CardDescription>Suggested preview - not submitted until confirmed.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {isAnalyzing ? (
            <div className="flex items-center gap-2 rounded-md border bg-muted/20 p-3 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" />
              Running LLM analysis...
            </div>
          ) : !shouldShowAnalyzedPreview ? (
            <div className="rounded-md border bg-muted/20 p-3 text-sm text-muted-foreground">
              {hasRequirementText
                ? "Click Analyze Requirement to preview suggested I/O, logic, and safety constraints."
                : "Enter a control requirement and analyze it to preview suggested I/O, logic, and safety constraints."}
            </div>
          ) : (
            <>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-md border bg-muted/40 p-3">
                  <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Detected domain</div>
                  <div className="mt-1 font-medium">{analysisPreview.domain}</div>
                </div>
                <div className="rounded-md border bg-muted/40 p-3">
                  <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
                    {analysisPreview.source === "llm" ? "LLM Analysis" : "Heuristic fallback"}
                  </div>
                  <div className="mt-1 font-medium">Confidence {(Number(analysisPreview.confidence) * 100).toFixed(0)}%</div>
                </div>
              </div>
              <EditableSignalList
                title="Inferred inputs"
                items={inferredInputs}
                tag="IN"
                emptyMessage="No inferred inputs."
                onChange={(nextItems) => {
                  setInferredInputs(nextItems);
                  syncConfirmedInputs(nextItems);
                }}
                onRemove={(index) => {
                  const nextItems = inferredInputs.filter((_, currentIndex) => currentIndex !== index);
                  setInferredInputs(nextItems);
                  syncConfirmedInputs(nextItems);
                }}
              />
              <div className="flex gap-2 rounded-md border bg-muted/20 p-2">
                <Input
                  placeholder="Input name"
                  value={newInputDraft.name}
                  onChange={(event) => setNewInputDraft((prev) => ({ ...prev, name: event.target.value }))}
                />
                <Input
                  placeholder="Type"
                  value={newInputDraft.type}
                  onChange={(event) =>
                    setNewInputDraft((prev) => ({
                      ...prev,
                      type: event.target.value.toUpperCase() as EditableSignal["type"]
                    }))
                  }
                />
                <Input
                  placeholder="Source"
                  value={newInputDraft.source ?? ""}
                  onChange={(event) =>
                    setNewInputDraft((prev) => ({
                      ...prev,
                      source: event.target.value as EditableSignal["source"]
                    }))
                  }
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    const name = normalizeSignalName(newInputDraft.name);
                    if (!name) return;
                    const nextSignal: EditableSignal = {
                      name,
                      type: newInputDraft.type || "BOOL",
                      source: newInputDraft.source || "Operator",
                      description: newInputDraft.description || ""
                    };
                    const nextItems = dedupeSignals([...inferredInputs, nextSignal]);
                    setInferredInputs(nextItems);
                    syncConfirmedInputs(nextItems);
                    setNewInputDraft({ name: "", type: "BOOL", source: "Operator", description: "" });
                  }}
                >
                  <Plus className="size-4" />
                </Button>
              </div>
              <EditableSignalList
                title="Confirmed outputs"
                items={confirmedOutputSignals}
                tag="OUT"
                emptyMessage="No confirmed outputs yet."
                onChange={(nextItems) => {
                  const currentConfirmed = [...confirmedOutputSignals];
                  setSuggestedOutputs((prev) => {
                    const next = [...prev];
                    currentConfirmed.forEach((current, index) => {
                      const foundIndex = next.findIndex((item) => item.name === current.name);
                      if (foundIndex >= 0 && nextItems[index]) {
                        next[foundIndex] = nextItems[index];
                      }
                    });
                    return dedupeSignals(next);
                  });
                  setConfirmedOutputs(nextItems.map((item) => item.name));
                }}
                onRemove={(index) => {
                  const target = confirmedOutputSignals[index];
                  if (!target) return;
                  setConfirmedOutputs((prev) => prev.filter((name) => name !== target.name));
                }}
              />
              <div>
                <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Suggested outputs (not yet confirmed)
                </div>
                <EditableSignalList
                  title="Suggested outputs"
                  items={visibleSuggestedOutputs}
                  tag="OUT"
                  emptyMessage="No suggested outputs."
                  onChange={(nextItems) => {
                    const currentVisible = [...visibleSuggestedOutputs];
                    setSuggestedOutputs((prev) =>
                      prev.map((item) => {
                        const currentIndex = currentVisible.findIndex((visibleItem) => visibleItem.name === item.name);
                        if (currentIndex === -1) return item;
                        return nextItems[currentIndex] ?? item;
                      })
                    );
                  }}
                  renderActions={(signal) => (
                    <>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => setConfirmedOutputs((prev) => (prev.includes(signal.name) ? prev : [...prev, signal.name]))}
                      >
                        Accept
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => setDismissedSuggestedOutputs((prev) => (prev.includes(signal.name) ? prev : [...prev, signal.name]))}
                      >
                        Remove
                      </Button>
                    </>
                  )}
                />
              </div>
              <div className="flex gap-2 rounded-md border bg-muted/20 p-2">
                <Input
                  placeholder="Output name"
                  value={newOutputDraft.name}
                  onChange={(event) => setNewOutputDraft((prev) => ({ ...prev, name: event.target.value }))}
                />
                <Input
                  placeholder="Type"
                  value={newOutputDraft.type}
                  onChange={(event) =>
                    setNewOutputDraft((prev) => ({
                      ...prev,
                      type: event.target.value.toUpperCase() as EditableSignal["type"]
                    }))
                  }
                />
                <Input
                  placeholder="Source"
                  value={newOutputDraft.source ?? ""}
                  onChange={(event) =>
                    setNewOutputDraft((prev) => ({
                      ...prev,
                      source: event.target.value as EditableSignal["source"]
                    }))
                  }
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    const name = normalizeSignalName(newOutputDraft.name);
                    if (!name) return;
                    const nextSignal: EditableSignal = {
                      name,
                      type: newOutputDraft.type || "BOOL",
                      source: newOutputDraft.source || "Operator",
                      description: newOutputDraft.description || ""
                    };
                    setSuggestedOutputs((prev) => dedupeSignals([...prev, nextSignal]));
                    setConfirmedOutputs((prev) => (prev.includes(name) ? prev : [...prev, name]));
                    setNewOutputDraft({ name: "", type: "BOOL", source: "Operator", description: "" });
                  }}
                >
                  <Plus className="size-4" />
                </Button>
              </div>
              <EditableSignalList
                title="Suggested internals"
                items={suggestedInternals}
                tag="INT"
                emptyMessage="No suggested internals."
                onChange={setSuggestedInternals}
              />
            </>
          )}
          <div>
            <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Safety constraints - {confirmedSafetyConstraints.length}
            </div>
            <div className="space-y-2 text-sm">
              {confirmedSafetyConstraints.map((constraint, index) => (
                <div key={constraint}><span className="mr-2 font-mono text-xs text-muted-foreground">SC{index + 1}</span>{constraint}</div>
              ))}
            </div>
          </div>
          <div className="rounded-md border border-sky-200 bg-sky-50 p-3 text-sm text-sky-800 dark:border-sky-900 dark:bg-sky-950/30 dark:text-sky-300">
            Continue to generate the canonical Plan Object, including I/O wiring, control logic, and IEC scope.
          </div>
        </CardContent>
      </Card>
    </form>
  );
}

type EditableSignal = {
  name: string;
  type: "BOOL" | "INT" | "REAL" | "TIME";
  source?: "Operator" | "Safety" | "Sensor" | "Timer";
  description?: string;
};

function dedupeSignals<T extends { name: string }>(signals: T[]) {
  return signals.filter((item, index, source) => source.findIndex((candidate) => candidate.name === item.name) === index);
}

function EditableSignalList({
  title,
  items,
  tag,
  emptyMessage,
  onChange,
  onRemove,
  renderActions
}: {
  title: string;
  items: EditableSignal[];
  tag: "IN" | "OUT" | "INT";
  emptyMessage: string;
  onChange: (nextItems: EditableSignal[]) => void;
  onRemove?: (index: number) => void;
  renderActions?: (signal: EditableSignal) => ReactNode;
}) {
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [draft, setDraft] = useState<EditableSignal>({ name: "", type: "BOOL", source: "Operator", description: "" });

  function beginEdit(index: number) {
    setEditingIndex(index);
    setDraft(items[index]);
  }

  return (
    <div>
      <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        {title} - {items.length}
      </div>
      <div className="space-y-2">
        {items.length > 0 ? items.map((item, index) => (
          <div className="rounded-md bg-muted px-3 py-2 text-xs" key={`${item.name}-${index}`}>
            {editingIndex === index ? (
              <div className="flex gap-2">
                <Input value={draft.name} onChange={(event) => setDraft((prev) => ({ ...prev, name: event.target.value }))} />
                <Input value={draft.type} onChange={(event) => setDraft((prev) => ({ ...prev, type: event.target.value.toUpperCase() as EditableSignal["type"] }))} />
                <Input value={draft.source ?? ""} onChange={(event) => setDraft((prev) => ({ ...prev, source: event.target.value as EditableSignal["source"] }))} />
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    const nextItems = [...items];
                    nextItems[index] = { ...draft, name: draft.name.trim().replace(/\s+/g, "_") };
                    onChange(nextItems);
                    setEditingIndex(null);
                  }}
                >
                  Save
                </Button>
                <Button type="button" size="sm" variant="outline" onClick={() => setEditingIndex(null)}>Cancel</Button>
              </div>
            ) : (
              <div className="flex items-center justify-between">
                <div className="font-mono">
                  <Badge tone={tag === "IN" ? "info" : "primary"} className="mr-2 font-mono">{tag}</Badge>
                  {item.name} <span className="text-muted-foreground">: {item.type}</span>
                  {item.source ? <span className="ml-2 text-muted-foreground">({item.source})</span> : null}
                </div>
                <div className="flex gap-2">
                  <Button type="button" size="sm" variant="outline" onClick={() => beginEdit(index)}>
                    <Pencil className="size-4" />
                  </Button>
                  {onRemove ? (
                    <Button type="button" size="sm" variant="outline" onClick={() => onRemove(index)}>
                      <X className="size-4" />
                    </Button>
                  ) : null}
                  {renderActions ? renderActions(item) : null}
                </div>
              </div>
            )}
          </div>
        )) : <div className="rounded-md border bg-muted/20 p-3 text-sm text-muted-foreground">{emptyMessage}</div>}
      </div>
    </div>
  );
}

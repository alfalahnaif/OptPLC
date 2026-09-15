"use client";

import { useState } from "react";
import { ArrowRight, Copy, Download, FileCode2 } from "lucide-react";
import { useRouter } from "next/navigation";

import { CodeGenerationModeBadge } from "@/components/common/code-generation-mode-badge";
import { CodePanel } from "@/components/common/code-panel";
import { MetricCard } from "@/components/common/metric-card";
import { PageStateGate, type PageState } from "@/components/common/page-state";
import { RepairLoopPanel } from "@/components/common/repair-loop-panel";
import { StatusBadge } from "@/components/common/status-badge";
import { PageHeader } from "@/components/layout/page-header";
import { PipelineStrip } from "@/components/layout/pipeline-strip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ACTIVE_PROJECT_ID, getCodePageData, projectPath, useApiResource, validateCode } from "@/lib/api-client";
import type { RAGSource } from "@/lib/api-contracts";

export function CodePage({ projectId = ACTIVE_PROJECT_ID, state }: { projectId?: string; state?: PageState } = {}) {
  const router = useRouter();
  const resource = useApiResource(() => getCodePageData(projectId), [projectId]);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);
  const [isRunningValidation, setIsRunningValidation] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const effectiveState = state ?? resource.state;
  const data = resource.data;
  async function handleRunValidation() {
    setValidationError(null);
    setIsRunningValidation(true);
    try {
      await validateCode(projectId);
      router.push(projectPath(projectId, "validation"));
    } catch (error) {
      setValidationError(error instanceof Error ? error.message : "Unable to run validation.");
    } finally {
      setIsRunningValidation(false);
    }
  }

  const stateView =
    effectiveState !== "ready" || !data ? (
      <PageStateGate
        state={effectiveState === "ready" ? "loading" : effectiveState}
        loading={{ title: "Loading Structured Text", description: "Preparing Monaco and the generated code artifact." }}
        empty={{ title: "No code artifact", description: "Generate Structured Text code before viewing this page." }}
        error={{
          title: "Code artifact unavailable",
          description: codeErrorDescription(resource.error)
        }}
      />
    ) : null;

  return (
    <>
      <PipelineStrip projectId={projectId} />
      <PageHeader
        eyebrow="Pipeline - Step 5 of 9"
        title="Generated Structured Text"
        description="IEC 61131-3 source emitted by the Code Generation Agent. Compare iterations and inspect the latest form."
        actions={
          <>
            <CodeGenerationModeBadge />
            <StatusBadge status="passed" label="Syntax OK" />
            <Button
              variant="outline"
              onClick={async () => {
                if (!data) return;
                await navigator.clipboard.writeText(data.source);
                setCopyStatus("Code copied to clipboard.");
              }}
            >
              <Copy /> Copy code
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                if (!data) return;
                const blob = new Blob([data.source], { type: "text/plain" });
                const href = URL.createObjectURL(blob);
                const link = document.createElement("a");
                link.href = href;
                link.download = data.artifact.filename || `plcforge_${projectId}.st`;
                document.body.appendChild(link);
                link.click();
                link.remove();
                URL.revokeObjectURL(href);
              }}
            >
              <Download /> Download .st
            </Button>
            <Button onClick={() => void handleRunValidation()} disabled={!data || isRunningValidation}>
              {isRunningValidation ? "Running validation..." : "Run validation"} <ArrowRight />
            </Button>
          </>
        }
      />
      {copyStatus ? <div className="mb-3 text-sm text-emerald-700">{copyStatus}</div> : null}
      {validationError ? (
        <div className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/30 dark:text-red-200">
          {validationError}
        </div>
      ) : null}
      {stateView ?? (data ? (
        <div className="space-y-5">
          <Card>
            <CardHeader>
              <CardTitle>Generated IEC 61131-3 Structured Text</CardTitle>
            </CardHeader>
          </Card>
          <div className="grid gap-5 xl:grid-cols-[1.5fr_.7fr]">
            {data.optimizationReport ? (
              <Tabs defaultValue="optimized">
                <TabsList>
                  <TabsTrigger value="generated">Generated</TabsTrigger>
                  <TabsTrigger value="optimized">Optimized</TabsTrigger>
                  <TabsTrigger value="diff">Diff</TabsTrigger>
                </TabsList>
                <TabsContent value="generated">
                  <CodePanel title={data.optimizationReport.originalCode.filename} code={data.optimizationReport.originalCode.source} height="760px" />
                </TabsContent>
                <TabsContent value="optimized">
                  <CodePanel title={data.optimizationReport.optimizedCode.filename} code={data.optimizationReport.optimizedCode.source} height="760px" />
                </TabsContent>
                <TabsContent value="diff">
                  <CodePanel
                    title="generated_vs_optimized.diff"
                    code={simpleDiff(data.optimizationReport.originalCode.source, data.optimizationReport.optimizedCode.source)}
                    height="760px"
                  />
                </TabsContent>
              </Tabs>
            ) : (
              <CodePanel title={data.artifact.filename} code={data.source} height="760px" />
            )}
            <div className="space-y-5">
              <Card>
                <CardHeader><CardTitle>Generation metadata</CardTitle></CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <Meta label="project_id" value={data.artifact.projectId} />
                  <Meta label="generator" value={data.artifact.metadata.generator} />
                  <Meta label="iteration" value={`${data.artifact.metadata.iteration}`} />
                  <Meta label="created_at" value={data.artifact.generatedAt} />
                  <Meta label="language" value={data.artifact.language} />
                  {data.optimizationReport ? (
                    <>
                      <Meta label="Optimizer" value={data.optimizationReport.optimizer} />
                      <Meta label="Optimization" value={data.optimizationReport.status} />
                    </>
                  ) : null}
                </CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle className="flex items-center gap-2"><FileCode2 className="size-4 text-primary" /> RAG sources used</CardTitle></CardHeader>
                <CardContent className="space-y-3 text-sm">
                  {(data.artifact.metadata?.ragSources?.length ?? 0) > 0 ? (
                    <div className="space-y-1">
                      {data.artifact.metadata?.ragSources?.map((src: RAGSource) => (
                        <div
                          key={src.id}
                          className="flex items-center justify-between text-sm"
                        >
                          <span className="flex items-center gap-1.5">
                            <span className="text-green-500 text-xs">●</span>
                            {src.name}
                          </span>
                          <span className="text-muted-foreground text-xs">
                            {src.domain} · {Math.round((src.similarity ?? 0) * 100)}%
                          </span>
                        </div>
                      ))}
                      <div className="text-xs text-muted-foreground mt-1">
                        Mode: {data.artifact.metadata.generationMode || "llm"}
                        {data.artifact.metadata.tokensUsed &&
                          ` · ${data.artifact.metadata.tokensUsed} tokens`}
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      No RAG sources used.
                    </p>
                  )}
                </CardContent>
              </Card>
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
                <MetricCard label="LOC" value={`${codeMetrics(data).loc}`} detail={codeMetrics(data).sourceLabel} />
                <MetricCard label="Cyclomatic" value={`${codeMetrics(data).cyclomaticComplexity}`} detail={codeMetrics(data).sourceLabel} />
                <MetricCard label="Maintainability" value={`${codeMetrics(data).maintainabilityIndex}`} detail={codeMetrics(data).sourceLabel} />
                <MetricCard label="Iteration" value={`${data.artifact.iteration}`} detail="generation pass" />
              </div>
              {codeMetrics(data).sourceLabel === "Not calculated yet" ? (
                <div className="rounded-md border bg-muted/20 p-3 text-sm text-muted-foreground">
                  Metrics not calculated yet. Open Metrics page to compute project metrics.
                </div>
              ) : null}
            </div>
          </div>
          {data.repairLoopReport ? <RepairLoopPanel report={data.repairLoopReport} /> : null}
        </div>
      ) : null)}
    </>
  );
}

function codeErrorDescription(error: Error | null) {
  const message = error?.message ?? "The generated source could not be loaded.";
  if (message.includes("PlanObject must be generated before code generation")) {
    return "Generate a Plan Object and Structured Text code before viewing this page.";
  }
  return message;
}

function codeMetrics(data: { artifact: { metrics?: { loc: number; cyclomaticComplexity: number; maintainabilityIndex: number } }; source: string }) {
  if (data.artifact.metrics?.loc != null && data.artifact.metrics?.cyclomaticComplexity != null) {
    return {
      loc: data.artifact.metrics.loc,
      cyclomaticComplexity: data.artifact.metrics.cyclomaticComplexity,
      maintainabilityIndex: data.artifact.metrics.maintainabilityIndex,
      sourceLabel: "Code metadata"
    };
  }
  const lines = data.source.split(/\r?\n/).map((line) => line.trim()).filter((line) => line && !line.startsWith("(*") && !line.startsWith("//"));
  return {
    loc: lines.length,
    cyclomaticComplexity: 1,
    maintainabilityIndex: 0,
    sourceLabel: "Client estimate"
  };
}

function simpleDiff(before: string, after: string) {
  const beforeLines = before.split(/\r?\n/);
  const afterLines = after.split(/\r?\n/);
  const max = Math.max(beforeLines.length, afterLines.length);
  const out: string[] = [];
  for (let index = 0; index < max; index += 1) {
    const b = beforeLines[index];
    const a = afterLines[index];
    if (b === a) {
      if (a != null) out.push(` ${a}`);
      continue;
    }
    if (b != null) out.push(`-${b}`);
    if (a != null) out.push(`+${a}`);
  }
  return out.join("\n");
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right font-medium">{value}</span>
    </div>
  );
}

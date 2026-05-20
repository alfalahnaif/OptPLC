"use client";

import Link from "next/link";
import { ArrowRight, Copy, Download, FileCode2 } from "lucide-react";

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
import { ACTIVE_PROJECT_ID, getCodePageData, projectPath, useApiResource } from "@/lib/api-client";

export function CodePage({ projectId = ACTIVE_PROJECT_ID, state }: { projectId?: string; state?: PageState } = {}) {
  const resource = useApiResource(() => getCodePageData(projectId), [projectId]);
  const effectiveState = state ?? resource.state;
  const data = resource.data;
  const stateView =
    effectiveState !== "ready" || !data ? (
      <PageStateGate
        state={effectiveState === "ready" ? "loading" : effectiveState}
        loading={{ title: "Loading Structured Text", description: "Preparing Monaco and the generated code artifact." }}
        empty={{ title: "No code artifact", description: "Approve a Plan Object to generate Structured Text." }}
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
        description="IEC 61131-3 source emitted by the Code Generation Agent. Compare iterations and inspect the verified form."
        actions={
          <>
            <CodeGenerationModeBadge />
            <StatusBadge status="passed" label="Syntax OK" />
            <Button variant="outline"><Copy /> Copy code</Button>
            <Button variant="outline"><Download /> Download .st</Button>
            <Button asChild><Link href={projectPath(projectId, "validation")}>Run validation <ArrowRight /></Link></Button>
          </>
        }
      />
      {stateView ?? (data ? (
        <div className="space-y-5">
          <div className="grid gap-5 xl:grid-cols-[1.5fr_.7fr]">
            {data.optimizationReport ? (
              <Tabs defaultValue="optimized">
                <TabsList>
                  <TabsTrigger value="generated">Generated</TabsTrigger>
                  <TabsTrigger value="optimized">Optimized</TabsTrigger>
                </TabsList>
                <TabsContent value="generated">
                  <CodePanel title={data.optimizationReport.originalCode.filename} code={data.optimizationReport.originalCode.source} />
                </TabsContent>
                <TabsContent value="optimized">
                  <CodePanel title={data.optimizationReport.optimizedCode.filename} code={data.optimizationReport.optimizedCode.source} />
                </TabsContent>
              </Tabs>
            ) : (
              <CodePanel title={data.artifact.filename} code={data.source} />
            )}
            <div className="space-y-5">
              <Card>
                <CardHeader><CardTitle>Generation metadata</CardTitle></CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <Meta label="Generator" value={data.artifact.metadata.generator} />
                  <Meta label="Iteration" value={`${data.artifact.metadata.iteration}`} />
                  <Meta label="Target" value="IEC 61131-3 ST" />
                  <Meta label="Runtime" value="CODESYS / TwinCAT" />
                  <Meta label="Generated" value={data.artifact.generatedAt} />
                  <Meta label="Artifact" value={data.artifact.artifactId} />
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
                  {data.ragSources.length > 0 ? data.ragSources.map((source) => (
                    <div className="flex justify-between rounded-md border bg-muted/30 p-3" key={source}>
                      <span>{source}</span>
                      <span className="text-xs text-muted-foreground">used</span>
                    </div>
                  )) : <div className="rounded-md border bg-muted/30 p-3 text-muted-foreground">No RAG sources used by the template generator.</div>}
                </CardContent>
              </Card>
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
                <MetricCard label="LOC" value={`${data.artifact.metrics.loc}`} detail="source lines" />
                <MetricCard label="Cyclomatic" value={`${data.artifact.metrics.cyclomaticComplexity}`} detail="branches" />
                <MetricCard label="Maintainability" value={`${data.artifact.metrics.maintainabilityIndex}`} detail="index" />
                <MetricCard label="Iteration" value={`${data.artifact.iteration}`} detail="generation pass" />
              </div>
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
    return "Generate a Plan Object before generating code.";
  }
  return message;
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right font-medium">{value}</span>
    </div>
  );
}

"use client";

import { useMemo, useState } from "react";
import { Beaker, Loader2, Play, RotateCcw } from "lucide-react";

import { BenchmarkModeBadge } from "@/components/common/benchmark-mode-badge";
import { PageStateGate, type PageState } from "@/components/common/page-state";
import { PageHeader } from "@/components/layout/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type {
  BenchmarkCaseCatalogItem,
  BenchmarkCaseResult,
  BenchmarkComparisonResult,
  BenchmarkMode,
  BenchmarkSummaryResponse
} from "@/lib/api-contracts";
import {
  compareBenchmarkModes,
  getBenchmarkCases,
  runBenchmarkCase,
  runBenchmarkSuite,
  useApiResource
} from "@/lib/api-client";

type BenchmarkTabMode = BenchmarkMode | "compare_all";

export function BenchmarkPage({ state }: { state?: PageState } = {}) {
  const resource = useApiResource(getBenchmarkCases, []);
  const effectiveState = state ?? resource.state;
  const cases = resource.data ?? [];
  const [selectedCaseId, setSelectedCaseId] = useState<string>("");
  const [tabMode, setTabMode] = useState<BenchmarkTabMode>("compare_all");
  const [singleResult, setSingleResult] = useState<BenchmarkCaseResult | null>(null);
  const [comparisonResult, setComparisonResult] = useState<BenchmarkComparisonResult | null>(null);
  const [suiteSummary, setSuiteSummary] = useState<BenchmarkSummaryResponse | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [isRunningSuite, setIsRunningSuite] = useState(false);

  const caseId = selectedCaseId || (cases?.[0] ? resolveCaseId(cases[0], 0) : "");
  const stateView =
    effectiveState !== "ready" || !cases ? (
      <PageStateGate
        state={effectiveState === "ready" ? "loading" : effectiveState}
        loading={{ title: "Loading benchmark suite", description: "Loading benchmark cases from API." }}
        empty={{ title: "No benchmark cases", description: "Add benchmark definitions to run the suite." }}
        error={{ title: "Benchmark suite unavailable", description: "Benchmark case metadata could not be loaded." }}
      />
    ) : null;

  const suiteStats = useMemo(() => {
    if (!suiteSummary) return null;
    const rows = suiteSummary.cases.map((item) => item.results);
    const avg = (values: number[]) =>
      values.length ? Number((values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(2)) : 0;

    const locReduction = avg(
      rows
        .map((row) => {
          const baseline = toCaseResult(row.rule_based)?.metrics.loc ?? null;
          const llm = toCaseResult(row.llm)?.metrics.loc ?? null;
          if (baseline === null || llm === null) return null;
          return baseline - llm;
        })
        .filter((value): value is number => value !== null)
    );
    const ccReduction = avg(
      rows
        .map((row) => {
          const baseline = toCaseResult(row.rule_based)?.metrics.cyclomaticComplexity ?? null;
          const llm = toCaseResult(row.llm)?.metrics.cyclomaticComplexity ?? null;
          if (baseline === null || llm === null) return null;
          return baseline - llm;
        })
        .filter((value): value is number => value !== null)
    );

    return { locReduction, ccReduction };
  }, [suiteSummary]);

  if (effectiveState === "loading") {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-muted-foreground">Loading benchmark cases...</p>
      </div>
    );
  }

  if (effectiveState === "error" || cases.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-muted-foreground">
          No benchmark cases found. Check that benchmark/cases/ directory contains JSON files and the backend is
          running.
        </p>
      </div>
    );
  }

  async function handleRunCurrent() {
    if (!caseId) return;
    setIsRunning(true);
    setRunError(null);
    try {
      if (tabMode === "compare_all") {
        const result = await compareBenchmarkModes(caseId);
        setComparisonResult(result);
        setSingleResult(null);
      } else {
        const result = await runBenchmarkCase(caseId, tabMode);
        setSingleResult(result);
        setComparisonResult(null);
      }
    } catch (error) {
      setRunError(error instanceof Error ? error.message : "Benchmark run failed.");
    } finally {
      setIsRunning(false);
    }
  }

  async function handleRunSuite() {
    setIsRunningSuite(true);
    setRunError(null);
    try {
      const suite = await runBenchmarkSuite();
      setSuiteSummary(suite.summary);
      const firstCase = suite.cases[0];
      if (firstCase) {
        setComparisonResult(firstCase);
        setSingleResult(null);
        setTabMode("compare_all");
        setSelectedCaseId(firstCase.caseId);
      }
    } catch (error) {
      setRunError(error instanceof Error ? error.message : "Benchmark suite run failed.");
    } finally {
      setIsRunningSuite(false);
    }
  }

  function handleReset() {
    setSingleResult(null);
    setComparisonResult(null);
    setSuiteSummary(null);
    setRunError(null);
  }

  return (
    <>
      <PageHeader
        eyebrow="System"
        title="Benchmark Suite"
        description="Thesis comparison runner across deterministic baseline, LLM-only, and LLM+RAG modes."
        actions={
          <>
            <BenchmarkModeBadge />
            <Button variant="outline" onClick={handleReset} disabled={isRunning || isRunningSuite}>
              <RotateCcw /> Reset
            </Button>
            <Button onClick={handleRunCurrent} disabled={isRunning || !caseId}>
              {isRunning ? <Loader2 className="animate-spin" /> : <Play />}
              Run Selected
            </Button>
            <Button onClick={handleRunSuite} disabled={isRunningSuite || !cases}>
              {isRunningSuite ? <Loader2 className="animate-spin" /> : <Beaker />}
              Run Benchmark Suite
            </Button>
          </>
        }
      />
      {stateView ??
        (cases ? (
          <>
            {runError ? (
              <Alert variant="destructive" className="mb-5">
                <AlertTitle>Benchmark execution failed</AlertTitle>
                <AlertDescription>{runError}</AlertDescription>
              </Alert>
            ) : null}

            <Card className="mb-4">
              <CardContent className="flex flex-col gap-4 p-4 lg:flex-row lg:items-center lg:justify-between">
                <div className="flex items-center gap-3">
                  <label className="text-sm text-muted-foreground" htmlFor="benchmark-case-select">
                    Case
                  </label>
                  <select
                    id="benchmark-case-select"
                    className="h-9 min-w-64 rounded-md border bg-background px-3 text-sm"
                    value={caseId}
                    onChange={(event) => setSelectedCaseId(event.target.value)}
                  >
                    {cases.map((entry, idx) => {
                      const id = resolveCaseId(entry, idx);
                      const name = resolveCaseName(entry, id);
                      return (
                        <option key={id} value={id}>
                          {id} - {name}
                        </option>
                      );
                    })}
                  </select>
                </div>
                <Tabs value={tabMode} onValueChange={(value) => setTabMode(value as BenchmarkTabMode)}>
                  <TabsList>
                    <TabsTrigger value="rule_based">Rule-Based</TabsTrigger>
                    <TabsTrigger value="llm">LLM Only</TabsTrigger>
                    <TabsTrigger value="llm_rag">LLM + RAG</TabsTrigger>
                    <TabsTrigger value="compare_all">Compare All</TabsTrigger>
                  </TabsList>
                </Tabs>
              </CardContent>
            </Card>

            {suiteSummary ? (
              <div className="mb-4 grid gap-4 md:grid-cols-4">
                <Summary label="Total runs" value={String(suiteSummary.totalRuns)} />
                <Summary label="Avg LOC reduction (LLM vs rule)" value={`${suiteStats?.locReduction ?? 0}`} />
                <Summary label="Avg CC reduction (LLM vs rule)" value={`${suiteStats?.ccReduction ?? 0}`} />
                <Summary label="Best mode" value={suiteSummary.bestMode} />
              </div>
            ) : null}

            {suiteSummary ? (
              <div className="mb-5 grid gap-4 md:grid-cols-3">
                <Summary
                  label="Checks-passed rate"
                  value={`Rule ${suiteSummary.byMode.rule_based.verificationRate}% / LLM ${suiteSummary.byMode.llm.verificationRate}% / RAG ${suiteSummary.byMode.llm_rag.verificationRate}%`}
                />
                <Summary
                  label="Average repair iterations"
                  value={`Rule ${suiteSummary.byMode.rule_based.avgRepairIterations} / LLM ${suiteSummary.byMode.llm.avgRepairIterations} / RAG ${suiteSummary.byMode.llm_rag.avgRepairIterations}`}
                />
                <Summary
                  label="Average complexity"
                  value={`Rule ${suiteSummary.byMode.rule_based.avgCC} / LLM ${suiteSummary.byMode.llm.avgCC} / RAG ${suiteSummary.byMode.llm_rag.avgCC}`}
                />
              </div>
            ) : null}

            <div className="grid gap-5 xl:grid-cols-[1fr_.42fr]">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Beaker className="size-4 text-primary" /> Benchmark output
                  </CardTitle>
                </CardHeader>
                <div className="overflow-x-auto">
                  {tabMode === "compare_all" ? (
                    <ComparisonTable comparison={comparisonResult} />
                  ) : (
                    <SingleModeTable result={singleResult} />
                  )}
                </div>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Execution details</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <SummaryRow label="Selected case" value={caseId || "-"} />
                  <SummaryRow label="Selected mode" value={tabMode} />
                  {singleResult ? (
                    <>
                      <SummaryRow
                        label="Status"
                        value={singleResult.verified ? "CHECKS_PASSED" : singleResult.validationStatus ?? "ERROR"}
                      />
                      <SummaryRow label="Generation time" value={`${singleResult.generationTimeMs} ms`} />
                      <SummaryRow label="Repair iterations" value={String(singleResult.repairIterations)} />
                      <SummaryRow label="LLM model" value={singleResult.llmModel ?? "-"} />
                    </>
                  ) : null}
                  {comparisonResult ? (
                    <>
                      <SummaryRow label="Rule status" value={statusText(toCaseResult(comparisonResult.results.rule_based))} />
                      <SummaryRow label="LLM status" value={statusText(toCaseResult(comparisonResult.results.llm))} />
                      <SummaryRow label="RAG status" value={statusText(toCaseResult(comparisonResult.results.llm_rag))} />
                    </>
                  ) : null}
                </CardContent>
              </Card>
            </div>
          </>
        ) : null)}
    </>
  );
}

function SingleModeTable({ result }: { result: BenchmarkCaseResult | null }) {
  if (!result) {
    return (
      <Table>
        <THead>
          <TR>
            <TH>Mode</TH>
            <TH>Status</TH>
            <TH>LOC</TH>
            <TH>CC</TH>
            <TH>MI</TH>
            <TH>Scan</TH>
            <TH>Time</TH>
          </TR>
        </THead>
        <TBody>
          <TR>
            <TD colSpan={7} className="text-sm text-muted-foreground">
              Run a mode to view result.
            </TD>
          </TR>
        </TBody>
      </Table>
    );
  }
  return (
    <Table>
      <THead>
        <TR>
          <TH>Mode</TH>
          <TH>Status</TH>
          <TH>LOC</TH>
          <TH>CC</TH>
          <TH>MI</TH>
          <TH>Scan</TH>
          <TH>Time</TH>
        </TR>
      </THead>
      <TBody>
        <TR>
          <TD className="font-medium">{result.mode}</TD>
          <TD>
            <ValidationStatusBadge status={result.validationStatus} />
          </TD>
          <TD>{result.metrics.loc}</TD>
          <TD>{result.metrics.cyclomaticComplexity}</TD>
          <TD>{result.metrics.maintainabilityIndex}</TD>
          <TD>{result.metrics.estimatedScanTimeMs} ms</TD>
          <TD>{result.generationTimeMs} ms</TD>
        </TR>
      </TBody>
    </Table>
  );
}

function ComparisonTable({ comparison }: { comparison: BenchmarkComparisonResult | null }) {
  const baseline = toCaseResult(comparison?.results.rule_based);
  const llm = toCaseResult(comparison?.results.llm);
  const rag = toCaseResult(comparison?.results.llm_rag);
  if (!baseline || !llm || !rag) {
    return (
      <Table>
        <THead>
          <TR>
            <TH>Metric</TH>
            <TH>Rule-Based</TH>
            <TH>LLM Only</TH>
            <TH>LLM+RAG</TH>
            <TH>Best</TH>
          </TR>
        </THead>
        <TBody>
          <TR>
            <TD colSpan={5} className="text-sm text-muted-foreground">
              Run compare mode to view table.
            </TD>
          </TR>
        </TBody>
      </Table>
    );
  }
  const bestLower = (rule: number, llmOnly: number, ragOnly: number) =>
    rule <= llmOnly && rule <= ragOnly ? "Rule-Based" : llmOnly <= ragOnly ? "LLM Only" : "LLM+RAG";
  const bestHigher = (rule: number, llmOnly: number, ragOnly: number) =>
    rule >= llmOnly && rule >= ragOnly ? "Rule-Based" : llmOnly >= ragOnly ? "LLM Only" : "LLM+RAG";
  return (
    <Table>
      <THead>
        <TR>
          <TH>Metric</TH>
          <TH>Rule-Based</TH>
          <TH>LLM Only</TH>
          <TH>LLM+RAG</TH>
          <TH>Best</TH>
        </TR>
      </THead>
      <TBody>
        <TR>
          <TD>Lines of Code</TD>
          <TD>{baseline.metrics.loc}</TD>
          <TD className={deltaClass(llm.metrics.loc - baseline.metrics.loc, false)}>{llm.metrics.loc}</TD>
          <TD className={deltaClass(rag.metrics.loc - baseline.metrics.loc, false)}>{rag.metrics.loc}</TD>
          <TD>{bestLower(baseline.metrics.loc, llm.metrics.loc, rag.metrics.loc)}</TD>
        </TR>
        <TR>
          <TD>Cyclomatic CC</TD>
          <TD>{baseline.metrics.cyclomaticComplexity}</TD>
          <TD className={deltaClass(llm.metrics.cyclomaticComplexity - baseline.metrics.cyclomaticComplexity, false)}>
            {llm.metrics.cyclomaticComplexity}
          </TD>
          <TD className={deltaClass(rag.metrics.cyclomaticComplexity - baseline.metrics.cyclomaticComplexity, false)}>
            {rag.metrics.cyclomaticComplexity}
          </TD>
          <TD>{bestLower(baseline.metrics.cyclomaticComplexity, llm.metrics.cyclomaticComplexity, rag.metrics.cyclomaticComplexity)}</TD>
        </TR>
        <TR>
          <TD>Maintainability</TD>
          <TD>{baseline.metrics.maintainabilityIndex}</TD>
          <TD className={deltaClass(llm.metrics.maintainabilityIndex - baseline.metrics.maintainabilityIndex, true)}>
            {llm.metrics.maintainabilityIndex}
          </TD>
          <TD className={deltaClass(rag.metrics.maintainabilityIndex - baseline.metrics.maintainabilityIndex, true)}>
            {rag.metrics.maintainabilityIndex}
          </TD>
          <TD>{bestHigher(baseline.metrics.maintainabilityIndex, llm.metrics.maintainabilityIndex, rag.metrics.maintainabilityIndex)}</TD>
        </TR>
        <TR>
          <TD>Repair Iterations</TD>
          <TD>{baseline.repairIterations}</TD>
          <TD className={deltaClass(llm.repairIterations - baseline.repairIterations, false)}>{llm.repairIterations}</TD>
          <TD className={deltaClass(rag.repairIterations - baseline.repairIterations, false)}>{rag.repairIterations}</TD>
          <TD>{bestLower(baseline.repairIterations, llm.repairIterations, rag.repairIterations)}</TD>
        </TR>
        <TR>
          <TD>Checks passed</TD>
          <TD>
            <ValidationStatusBadge status={baseline.validationStatus} />
          </TD>
          <TD>
            <ValidationStatusBadge status={llm.validationStatus} />
          </TD>
          <TD>
            <ValidationStatusBadge status={rag.validationStatus} />
          </TD>
          <TD>-</TD>
        </TR>
        <TR>
          <TD>Generation Time</TD>
          <TD>{baseline.generationTimeMs} ms</TD>
          <TD>{(llm.generationTimeMs / 1000).toFixed(1)} s</TD>
          <TD>{(rag.generationTimeMs / 1000).toFixed(1)} s</TD>
          <TD>{bestLower(baseline.generationTimeMs, llm.generationTimeMs, rag.generationTimeMs)}</TD>
        </TR>
      </TBody>
    </Table>
  );
}

// Results stored before D-033 still say VERIFIED. It only ever meant that the checks passed.
function displayStatus(status?: string | null) {
  return status === "VERIFIED" ? "CHECKS_PASSED" : status;
}

function ValidationStatusBadge({ status: rawStatus }: { status?: string | null }) {
  const status = displayStatus(rawStatus);
  if (status === "CHECKS_PASSED") return <Badge tone="success">CHECKS_PASSED</Badge>;
  if (status === "SYNTAX_ERROR") return <Badge tone="danger">SYNTAX_ERROR</Badge>;
  if (status === "FORMAL_VIOLATION") return <Badge tone="warning">FORMAL_VIOLATION</Badge>;
  return <Badge tone="neutral">{status ?? "UNKNOWN"}</Badge>;
}

function toCaseResult(value: unknown): BenchmarkCaseResult | null {
  if (!value || typeof value !== "object") return null;
  if (!("caseId" in value)) return null;
  return value as BenchmarkCaseResult;
}

function resolveCaseId(entry: BenchmarkCaseCatalogItem, idx: number): string {
  return entry.id ?? entry.caseId ?? entry.case_id ?? `case-${idx}`;
}

function resolveCaseName(entry: BenchmarkCaseCatalogItem, fallbackId: string): string {
  return entry.name ?? entry.caseName ?? entry.title ?? fallbackId;
}

function statusText(value: BenchmarkCaseResult | null): string {
  if (!value) return "-";
  return displayStatus(value.validationStatus) ?? (value.verified ? "CHECKS_PASSED" : "FAILED");
}

function deltaClass(delta: number, higherIsBetter: boolean): string {
  if (delta === 0) return "";
  const improved = higherIsBetter ? delta > 0 : delta < 0;
  return improved ? "text-emerald-600" : "text-red-600";
}

function Summary({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</div>
        <div className="mt-3 text-3xl font-semibold">{value}</div>
      </CardContent>
    </Card>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono">{value}</span>
    </div>
  );
}

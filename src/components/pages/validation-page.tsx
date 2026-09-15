"use client";

import { useState, type ReactNode } from "react";
import { ArrowRight, CheckCircle2, Clock, ShieldCheck, TriangleAlert, XCircle } from "lucide-react";
import { useRouter } from "next/navigation";

import { PageStateGate, type PageState } from "@/components/common/page-state";
import { EvidenceBadge, SafetyScopeNotice } from "@/components/common/evidence-badge";
import { RepairLoopPanel } from "@/components/common/repair-loop-panel";
import { StatusBadge } from "@/components/common/status-badge";
import { ValidationModeBadge } from "@/components/common/validation-mode-badge";
import { PageHeader } from "@/components/layout/page-header";
import { PipelineStrip } from "@/components/layout/pipeline-strip";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import type { ValidationReport, ValidationStatus } from "@/lib/api-contracts";
import { ACTIVE_PROJECT_ID, debugCode, getValidationPageData, optimizeCode, projectPath, useApiResource, validateCode } from "@/lib/api-client";

export function ValidationPage({ projectId = ACTIVE_PROJECT_ID, state }: { projectId?: string; state?: PageState } = {}) {
  const router = useRouter();
  const [reloadToken, setReloadToken] = useState(0);
  const [isRunningValidation, setIsRunningValidation] = useState(false);
  const [runValidationError, setRunValidationError] = useState<string | null>(null);
  const [isRunningNextStep, setIsRunningNextStep] = useState(false);
  const [nextStepError, setNextStepError] = useState<string | null>(null);
  const resource = useApiResource(() => getValidationPageData(projectId), [projectId, reloadToken]);
  const effectiveState = state ?? resource.state;
  const data = resource.data;
  const report = data?.report;
  async function handleRunValidationNow() {
    setRunValidationError(null);
    setIsRunningValidation(true);
    try {
      await validateCode(projectId);
      setReloadToken((value) => value + 1);
    } catch (error) {
      setRunValidationError(error instanceof Error ? error.message : "Unable to run validation.");
    } finally {
      setIsRunningValidation(false);
    }
  }
  async function handleNextStep() {
    if (!report) return;
    setNextStepError(null);
    setIsRunningNextStep(true);
    try {
      if (report.status === "CHECKS_PASSED") {
        await optimizeCode(projectId);
        router.push(projectPath(projectId, "optimization"));
      } else {
        await debugCode(projectId);
        router.push(projectPath(projectId, "debugging"));
      }
    } catch (error) {
      setNextStepError(error instanceof Error ? error.message : "Unable to continue.");
    } finally {
      setIsRunningNextStep(false);
    }
  }

  const isEmpty = effectiveState === "empty" || (effectiveState === "ready" && !report);
  const stateView =
    effectiveState === "loading" || effectiveState === "error" ? (
      <PageStateGate
        state={effectiveState}
        loading={{ title: "Running validation", description: "Checking Structured Text syntax and static domain safety rules." }}
        error={{
          title: "Validation report unavailable",
          description: validationErrorDescription(resource.error)
        }}
      />
    ) : null;

  return (
    <>
      <PipelineStrip projectId={projectId} />
      <PageHeader
        eyebrow="Pipeline - Step 6 of 9"
        title="Validation results"
        description="Static checks by the Validation Agent before debugging or optimization. Passing them is not formal verification."
        actions={
          <>
            <ValidationModeBadge />
            {report ? <ValidationStatusBadge status={report.status} /> : null}
            {report ? (
              <ValidationNextAction
                status={report.status}
                onClick={() => void handleNextStep()}
                loading={isRunningNextStep}
              />
            ) : null}
          </>
        }
      />
      {nextStepError ? (
        <div className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/30 dark:text-red-200">
          {nextStepError}
        </div>
      ) : null}
      {stateView ?? (report ? (
        <div className="space-y-5">
          <ValidationReportView report={report} />
          {data?.repairLoopReport ? <RepairLoopPanel report={data.repairLoopReport} /> : null}
        </div>
      ) : isEmpty ? (
        <Card>
          <CardContent className="flex min-h-72 flex-col items-center justify-center gap-3 text-center">
            <div className="text-base font-semibold">No validation report</div>
            <p className="max-w-md text-sm text-muted-foreground">
              Run validation from the Generated Code page before viewing results.
            </p>
            {runValidationError ? (
              <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/30 dark:text-red-200">
                {runValidationError}
              </div>
            ) : null}
            <Button onClick={() => void handleRunValidationNow()} disabled={isRunningValidation}>
              {isRunningValidation ? "Running validation..." : "Run validation now"}
            </Button>
          </CardContent>
        </Card>
      ) : null)}
    </>
  );
}

function ValidationReportView({ report }: { report: ValidationReport }) {
  const safetyResults = report.safetyResults.length > 0 ? report.safetyResults : report.properties;
  const passedCount = safetyResults.filter((result) => result.status === "passed").length;
  const counterexamples = report.counterexamples.length > 0 ? report.counterexamples : report.counterexample ?? [];
  const checksPassed = report.status === "CHECKS_PASSED";

  return (
    <>
      <Card className="mb-5 overflow-hidden">
        <CardContent className="grid p-0 md:grid-cols-[1fr_2fr]">
          <div className={checksPassed ? "bg-emerald-50 p-6 dark:bg-emerald-950/20" : "bg-amber-50 p-6 dark:bg-amber-950/20"}>
            <div className={checksPassed ? "flex items-center gap-3 text-emerald-700 dark:text-emerald-300" : "flex items-center gap-3 text-amber-700 dark:text-amber-300"}>
              {checksPassed ? <CheckCircle2 className="size-5" /> : <TriangleAlert className="size-5" />}
              <span className="text-xs font-semibold uppercase tracking-wider">{report.status.replace("_", " ")}</span>
            </div>
            <div className="mt-2 text-2xl font-semibold">
              {checksPassed ? "Static checks passed" : report.status === "SYNTAX_ERROR" ? "Syntax checks failed" : "Safety checks failed"}
            </div>
            <div className="mt-3"><EvidenceBadge level={report.evidenceLevel} /></div>
            <p className="mt-4 text-sm text-muted-foreground">{report.summary}</p>
          </div>
          <div className="grid gap-0 md:grid-cols-4">
            <Summary label="Iteration" value={report.iteration} />
            <Summary label="Properties" value={`${passedCount}/${safetyResults.length}`} />
            <Summary label="Syntax" value={report.syntaxPassed ? "Passed" : "Failed"} />
            <Summary label="Validator" value={report.validator} />
            <div className="col-span-full flex items-center justify-between border-t p-5 text-sm text-muted-foreground">
              <span>Formal mode: <strong className="text-foreground">{report.solver}</strong></span>
              <span className="inline-flex items-center gap-2"><Clock className="size-4" /> {formatCheckedAt(report.checkedAt)}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="mb-5"><SafetyScopeNotice /></div>

      <div className="grid gap-5 xl:grid-cols-2">
        <div className="space-y-5">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Syntax check</CardTitle>
              <StatusBadge status={report.syntaxPassed ? "passed" : "failed"} />
            </CardHeader>
            <CardContent>
              {report.syntaxErrors.length > 0 ? <ErrorTable errors={report.syntaxErrors} /> : (
                <div className="space-y-2 text-sm">
                  <CheckLine>PROGRAM/FUNCTION_BLOCK structure is present</CheckLine>
                  <CheckLine>VAR_INPUT, VAR_OUTPUT, and END_VAR structure is valid</CheckLine>
                  <CheckLine>Assignments and declarations conform to IEC Structured Text checks</CheckLine>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Static safety rules</CardTitle>
              <StatusBadge status={report.formalPassed ? "passed" : "failed"} />
            </CardHeader>
            <CardContent>
              <div className="mb-2 flex justify-between text-sm">
                <span>Safety rules passed</span>
                <span className="font-mono">{passedCount} / {safetyResults.length}</span>
              </div>
              <Progress value={safetyResults.length ? (passedCount / safetyResults.length) * 100 : 0} />
              {report.formalErrors.length > 0 ? (
                <div className="mt-4 space-y-2">
                  {report.formalErrors.map((error) => (
                    <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/30 dark:text-red-200" key={error}>
                      {error}
                    </div>
                  ))}
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Safety results</CardTitle></CardHeader>
            <div className="overflow-x-auto">
              <Table>
                <THead><TR><TH>ID</TH><TH>Check</TH><TH>Details</TH><TH>Status</TH></TR></THead>
                <TBody>
                  {safetyResults.map((result) => (
                    <TR key={result.id}>
                      <TD className="font-mono text-xs">{result.id}</TD>
                      <TD>{result.description}</TD>
                      <TD className="text-muted-foreground">{result.details ?? "-"}</TD>
                      <TD><StatusBadge status={result.status} /></TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </div>
          </Card>
        </div>

        <div className="space-y-5">
          <Card className="min-h-60">
            <CardContent className="flex min-h-60 flex-col items-center justify-center text-center">
              {counterexamples.length > 0 ? (
                <>
                  <XCircle className="mb-4 size-10 text-red-700" />
                  <div className="font-semibold">Counterexamples found</div>
                  <p className="mt-2 max-w-sm text-sm text-muted-foreground">The static validator produced example failing states for debugging.</p>
                  <div className="mt-4 w-full space-y-2 text-left">
                    {counterexamples.map((example, index) => (
                      <pre className="overflow-auto rounded-md border bg-muted/40 p-3 text-xs" key={`${index}-${JSON.stringify(example)}`}>{JSON.stringify(example, null, 2)}</pre>
                    ))}
                  </div>
                </>
              ) : (
                <>
                  <ShieldCheck className="mb-4 size-10 text-emerald-700" />
                  <div className="font-semibold">No counterexample</div>
                  <p className="mt-2 max-w-sm text-sm text-muted-foreground">No static rule reported a failing state. The rules are text checks, not a proof.</p>
                </>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TriangleAlert className="size-4 text-warning" /> Errors and warnings - {report.errors.length}
              </CardTitle>
            </CardHeader>
            <CardContent className={report.errors.length > 0 ? "space-y-2" : "flex min-h-44 flex-col items-center justify-center text-center"}>
              {report.errors.length > 0 ? report.errors.map((error) => (
                <div className="rounded-md border bg-muted/30 p-3 text-sm" key={error}>{error}</div>
              )) : (
                <>
                  <CheckCircle2 className="mb-4 size-8 text-emerald-700" />
                  <div className="font-semibold">Clean run</div>
                  <p className="mt-1 text-sm text-muted-foreground">No errors or warnings reported.</p>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}

function ValidationStatusBadge({ status }: { status: ValidationStatus }) {
  const tone = status === "CHECKS_PASSED" ? "success" : status === "TIMEOUT" ? "warning" : "danger";
  return <Badge tone={tone} dot>{status}</Badge>;
}

function ValidationNextAction({
  status,
  onClick,
  loading
}: {
  status: ValidationStatus;
  onClick: () => void;
  loading: boolean;
}) {
  const passed = status === "CHECKS_PASSED";
  return (
    <Button onClick={onClick} disabled={loading}>
      {passed ?(loading ? "Running optimization..." : "Continue to Optimization") : (loading ? "Preparing debugging advice..." : "Open Debugging Advice")} <ArrowRight />
    </Button>
  );
}

function CheckLine({ children }: { children: ReactNode }) {
  return <div className="flex items-center gap-2"><CheckCircle2 className="size-4 text-emerald-700" /> {children}</div>;
}

function ErrorTable({ errors }: { errors: string[] }) {
  return (
    <Table>
      <THead><TR><TH>#</TH><TH>Syntax error</TH></TR></THead>
      <TBody>
        {errors.map((error, index) => (
          <TR key={error}>
            <TD className="font-mono text-xs">{index + 1}</TD>
            <TD>{error}</TD>
          </TR>
        ))}
      </TBody>
    </Table>
  );
}

function validationErrorDescription(error: Error | null) {
  const message = error?.message ?? "The validation report could not be loaded.";
  if (message.includes("CodeArtifact must be generated before validation")) {
    return "Generate Structured Text code before running validation.";
  }
  if (message.includes("PlanObject must be generated before validation")) {
    return "Generate a Plan Object before running validation.";
  }
  return message;
}

function formatCheckedAt(value: string) {
  if (!value) return "Not checked";
  return value.replace("T", " ").replace("+00:00", " UTC").replace("Z", " UTC");
}

function Summary({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="border-b border-r p-5 md:border-b-0">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-2 font-semibold">{value}</div>
    </div>
  );
}

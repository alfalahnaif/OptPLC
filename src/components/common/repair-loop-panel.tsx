import { CheckCircle2, GitBranch, ShieldCheck, Wrench, XCircle } from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import type { RepairLoopReport } from "@/lib/api-contracts";

export function RepairLoopPanel({ report }: { report: RepairLoopReport }) {
  const statusTone = report.finalStatus === "VERIFIED" ? "success" : report.finalStatus === "ITERATION_LIMIT_REACHED" ? "warning" : "danger";

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2"><Wrench className="size-4 text-primary" /> Repair loop</CardTitle>
        <Badge tone={statusTone} dot>{report.finalStatus}</Badge>
      </CardHeader>
      <CardContent className="space-y-5">
        <p className="text-sm text-muted-foreground">{report.summary}</p>
        <div className="grid gap-3 md:grid-cols-4">
          <Metric icon={<GitBranch className="size-4" />} label="Iterations" value={`${report.iterations}`} />
          <Metric icon={<Wrench className="size-4" />} label="Code versions" value={`${report.codeVersions.length}`} />
          <Metric icon={<ShieldCheck className="size-4" />} label="Validation" value={report.finalValidationReport.status} />
          <Metric icon={report.finalStatus === "VERIFIED" ? <CheckCircle2 className="size-4" /> : <XCircle className="size-4" />} label="Final code" value={`Iter ${report.finalCodeArtifact.iteration}`} />
        </div>

        <div className="overflow-x-auto">
          <Table>
            <THead>
              <TR><TH>Iter</TH><TH>Validation</TH><TH>Debugging</TH><TH>Generated code</TH></TR>
            </THead>
            <TBody>
              {report.validationReports.map((validation, index) => {
                const debug = report.debuggingReports[index];
                const code = report.codeVersions[index + 1] ?? report.codeVersions[index];
                return (
                  <TR key={`${validation.artifactId}-${index}`}>
                    <TD className="font-mono text-xs">{index + 1}</TD>
                    <TD><Badge tone={validation.status === "VERIFIED" ? "success" : validation.status === "TIMEOUT" ? "warning" : "danger"}>{validation.status}</Badge></TD>
                    <TD>{debug ? <Badge tone={debug.status === "PATCH_ADVICE_GENERATED" ? "warning" : "neutral"}>{debug.status}</Badge> : <span className="text-muted-foreground">-</span>}</TD>
                    <TD className="font-mono text-xs">{code?.artifactId ?? "-"}</TD>
                  </TR>
                );
              })}
            </TBody>
          </Table>
        </div>

        {report.debuggingReports.length > 0 ? (
          <div className="space-y-2">
            <div className="text-sm font-medium">Debugging advice used</div>
            {report.debuggingReports.map((debug) => (
              <div className="rounded-md border bg-muted/30 p-3 text-sm" key={`${debug.sourceArtifactId}-${debug.errorType}`}>
                <div className="font-medium">{debug.affectedCodeRegion}</div>
                <div className="mt-1 text-muted-foreground">{debug.patchAdvice[0]}</div>
              </div>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function Metric({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-md border bg-muted/30 p-3">
      <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground">{icon}{label}</div>
      <div className="mt-2 font-semibold">{value}</div>
    </div>
  );
}

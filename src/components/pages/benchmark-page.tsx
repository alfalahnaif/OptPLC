"use client";

import { Beaker, Play, RotateCcw } from "lucide-react";

import { PageStateGate, type PageState } from "@/components/common/page-state";
import { StatusBadge, type Status } from "@/components/common/status-badge";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { getBenchmarkSuiteData, useApiResource } from "@/lib/api-client";

export function BenchmarkPage({ state }: { state?: PageState } = {}) {
  const resource = useApiResource(getBenchmarkSuiteData, []);
  const effectiveState = state ?? resource.state;
  const data = resource.data;
  const stateView =
    effectiveState !== "ready" || !data ? (
      <PageStateGate
        state={effectiveState === "ready" ? "loading" : effectiveState}
        loading={{ title: "Loading benchmark suite", description: "Preparing representative PLC benchmark cases." }}
        empty={{ title: "No benchmark cases", description: "Add benchmark definitions to run the suite." }}
        error={{ title: "Benchmark suite unavailable", description: "The mock benchmark data could not be rendered." }}
      />
    ) : null;

  return (
    <>
      <PageHeader
        eyebrow="System"
        title="Benchmark Suite"
        description="Regression suite for representative PLC control problems using mocked agent results."
        actions={
          <>
            <Button variant="outline"><RotateCcw /> Reset suite</Button>
            <Button><Play /> Run benchmarks</Button>
          </>
        }
      />
      {stateView ?? (data ? (
        <>
      <div className="grid gap-4 md:grid-cols-4">
        <Summary label="Cases" value="20" />
        <Summary label="Pass rate" value="94%" />
        <Summary label="Avg runtime" value="31.8 s" />
        <Summary label="Avg LOC reduction" value="33.5%" />
      </div>
      <div className="mt-5 grid gap-5 xl:grid-cols-[1fr_.42fr]">
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Beaker className="size-4 text-primary" /> Benchmark cases</CardTitle></CardHeader>
          <div className="overflow-x-auto">
            <Table>
              <THead><TR><TH>ID</TH><TH>Name</TH><TH>Domain</TH><TH>Complexity</TH><TH>Status</TH><TH>Runtime</TH><TH>Gain</TH></TR></THead>
              <TBody>
                {data.benchmarkCases.map((test) => (
                  <TR key={test.id}>
                    <TD className="font-mono text-xs">{test.id}</TD>
                    <TD className="font-medium">{test.name}</TD>
                    <TD>{test.domain}</TD>
                    <TD>{test.complexity}</TD>
                    <TD><StatusBadge status={test.status as Status} /></TD>
                    <TD>{test.time}</TD>
                    <TD>{test.gain}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </div>
        </Card>
        <Card>
          <CardHeader><CardTitle>Suite coverage</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            {[
              ["Motor Control", 92],
              ["Process Control", 84],
              ["Traffic Control", 88],
              ["Safety Interlocks", 78],
              ["Sequential Batch", 71]
            ].map(([label, value]) => (
              <div key={label as string}>
                <div className="mb-1 flex justify-between text-sm"><span>{label}</span><span>{value}%</span></div>
                <Progress value={value as number} />
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
        </>
      ) : null)}
    </>
  );
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

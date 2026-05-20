"use client";

import Link from "next/link";
import { ArrowRight, CalendarDays, Filter } from "lucide-react";

import { PageStateGate, type PageState } from "@/components/common/page-state";
import { StatusBadge, type Status } from "@/components/common/status-badge";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { getProjectHistoryData, projectPath, useApiResource } from "@/lib/api-client";

export function HistoryPage({ state }: { state?: PageState } = {}) {
  const resource = useApiResource(getProjectHistoryData, []);
  const effectiveState = state ?? resource.state;
  const data = resource.data;
  const stateView =
    effectiveState !== "ready" || !data ? (
      <PageStateGate
        state={effectiveState === "ready" ? "loading" : effectiveState}
        loading={{ title: "Loading project history", description: "Preparing previous PLC agent sessions." }}
        empty={{ title: "No project history", description: "Completed projects will appear here." }}
        error={{ title: "Project history unavailable", description: resource.error?.message ?? "The history table could not be loaded." }}
      />
    ) : null;

  return (
    <>
      <PageHeader
        eyebrow="Overview"
        title="Project History"
        description="Past PLC agent sessions, validation outcomes, and optimization summaries."
        actions={
          <>
            <Button variant="outline"><CalendarDays /> Last 30 days</Button>
            <Button variant="outline"><Filter /> Filter</Button>
          </>
        }
      />
      {stateView ?? (data ? <Card>
        <CardHeader><CardTitle>All projects</CardTitle></CardHeader>
        <div className="overflow-x-auto">
          <Table>
            <THead><TR><TH>Project</TH><TH>Domain</TH><TH>Updated</TH><TH>Iterations</TH><TH>Complexity delta</TH><TH>Status</TH><TH></TH></TR></THead>
            <TBody>
              {data.projects.concat(data.projects.slice(1, 4)).map((project, index) => (
                <TR key={`${project.id}-${index}`}>
                  <TD>
                    <div className="font-medium">{project.name}</div>
                    <div className="font-mono text-xs text-muted-foreground">{project.id}</div>
                  </TD>
                  <TD>{project.domain}</TD>
                  <TD className="font-mono text-xs">{project.updated}</TD>
                  <TD>{project.iterations}</TD>
                  <TD>{project.delta}</TD>
                  <TD><StatusBadge status={project.status as Status} /></TD>
                  <TD><Button variant="ghost" size="sm" asChild><Link href={projectPath(project.id, "report")}>Open <ArrowRight /></Link></Button></TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </div>
      </Card> : null)}
    </>
  );
}

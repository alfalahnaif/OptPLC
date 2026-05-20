"use client";

import Link from "next/link";
import { ArrowRight, FileCode2, GitBranch, ShieldCheck } from "lucide-react";

import { PageStateGate, type PageState } from "@/components/common/page-state";
import { StatusBadge } from "@/components/common/status-badge";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ACTIVE_PROJECT_ID, getProject, projectPath, useApiResource } from "@/lib/api-client";

export function ProjectOverviewPage({ projectId = ACTIVE_PROJECT_ID, state }: { projectId?: string; state?: PageState } = {}) {
  const resource = useApiResource(() => getProject(projectId), [projectId]);
  const effectiveState = state ?? resource.state;
  const project = resource.data;
  const stateView =
    effectiveState !== "ready" || !project ? (
      <PageStateGate
        state={effectiveState === "ready" ? "loading" : effectiveState}
        loading={{ title: "Loading project workspace", description: "Preparing project metadata from the mock API client." }}
        empty={{ title: "Project not found", description: "No mock project matched this route." }}
        error={{ title: "Project unavailable", description: resource.error?.message ?? "The project client could not load this workspace." }}
      />
    ) : null;

  return (
    <>
      <PageHeader
        eyebrow={`Project ${projectId}`}
        title={project?.name ?? "Project workspace"}
        description="Project-based route shell prepared for future backend integration."
        actions={
          project ? (
            <>
              <StatusBadge status={project.status === "failed" ? "failed" : "optimized"} />
              <Button asChild>
                <Link href={projectPath(projectId, "requirements")}>
                  Open pipeline
                  <ArrowRight />
                </Link>
              </Button>
            </>
          ) : null
        }
      />
      {stateView ?? (project ? (
        <div className="grid gap-5 xl:grid-cols-[1fr_.7fr]">
          <Card>
            <CardHeader>
              <CardTitle>Project envelope</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2">
              <Info label="Project ID" value={project.id} />
              <Info label="Domain" value={project.domain} />
              <Info label="Standard" value={project.standard} />
              <Info label="Target language" value={project.targetLanguage} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Pipeline entry points</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Button variant="outline" className="w-full justify-start" asChild>
                <Link href={projectPath(projectId, "plan")}><GitBranch /> Plan Object</Link>
              </Button>
              <Button variant="outline" className="w-full justify-start" asChild>
                <Link href={projectPath(projectId, "code")}><FileCode2 /> Generated Code</Link>
              </Button>
              <Button variant="outline" className="w-full justify-start" asChild>
                <Link href={projectPath(projectId, "validation")}><ShieldCheck /> Validation Results</Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      ) : null)}
    </>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border bg-muted/30 p-4">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-2 font-medium">{value}</div>
    </div>
  );
}

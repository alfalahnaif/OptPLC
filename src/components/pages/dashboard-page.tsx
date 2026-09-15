"use client";

import Link from "next/link";
import { ArrowRight, Download, Plus, Server } from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import { MetricCard } from "@/components/common/metric-card";
import { PageStateGate, type PageState } from "@/components/common/page-state";
import { StatusBadge, type Status } from "@/components/common/status-badge";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { getDashboardData, useApiResource } from "@/lib/api-client";

export function DashboardPage({ state }: { state?: PageState } = {}) {
  const resource = useApiResource(getDashboardData, []);
  const effectiveState = state ?? resource.state;
  const data = resource.data;
  const stateView =
    effectiveState !== "ready" || !data ? (
      <PageStateGate
        state={effectiveState === "ready" ? "loading" : effectiveState}
        loading={{ title: "Loading dashboard", description: "Collecting pipeline health and recent project metrics." }}
        empty={{ title: "No dashboard metrics", description: "Create a PLC project to populate the dashboard." }}
        error={{ title: "Dashboard unavailable", description: resource.error?.message ?? "Dashboard data could not be loaded." }}
      />
    ) : null;

  return (
    <>
      <PageHeader
        eyebrow="Overview - 2026 Q2"
        title="Dashboard"
        description="Pipeline health, optimization yield, and recent agent sessions across all engineering projects."
        actions={
          <>
            <Button variant="outline">
              <Download />
              Export report
            </Button>
            <Button asChild>
              <Link href="/new-project">
                <Plus />
                New PLC Project
              </Link>
            </Button>
          </>
        }
      />

      {stateView ?? (data ? (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            {data.dashboardKpis.map((kpi) => (
              <MetricCard key={kpi.label} {...kpi} />
            ))}
          </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[2fr_1fr]">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Optimization improvements over time</CardTitle>
              <CardDescription>Average delta across all sessions, last 12 weeks</CardDescription>
            </div>
            <div className="rounded-md border bg-muted/50 px-3 py-1.5 font-mono text-xs">12w</div>
          </CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.trendData} margin={{ left: 0, right: 8, top: 10, bottom: 0 }}>
                <defs>
                  <linearGradient id="complexity" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="5%" stopColor="#315fd1" stopOpacity={0.24} />
                    <stop offset="95%" stopColor="#315fd1" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
                <XAxis dataKey="week" tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }} />
                <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }} />
                <Tooltip contentStyle={{ borderRadius: 8, borderColor: "hsl(var(--border))" }} />
                <Area dataKey="complexity" name="Complexity delta %" stroke="#315fd1" fill="url(#complexity)" strokeWidth={2} />
                <Area dataKey="maintainability" name="Maintainability delta pts" stroke="#0e8fb5" fill="transparent" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <div className="space-y-5">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Server className="size-4 text-primary" />
                System status
              </CardTitle>
              <CardDescription>Service health checked 12 seconds ago</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {data.serviceStatus.map((service) => {
                const Icon = service.icon;
                return (
                  <div className="flex items-center justify-between rounded-md border bg-muted/30 p-3" key={service.name}>
                    <div className="flex items-center gap-3">
                      <span className="grid size-8 place-items-center rounded-md bg-card">
                        <Icon className="size-4" />
                      </span>
                      <div>
                        <div className="text-sm font-medium">{service.name}</div>
                        <div className="text-xs text-muted-foreground">{service.detail}</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <StatusBadge status="healthy" />
                      <div className="mt-1 font-mono text-[11px] text-muted-foreground">{service.latency}</div>
                    </div>
                  </div>
                );
              })}
            </CardContent>
          </Card>
          <Card className="border-foreground bg-foreground text-background">
            <CardContent className="p-5">
              <div className="text-base font-semibold">Start a new PLC project</div>
              <p className="mt-2 max-w-sm text-sm text-background/75">
                Define a control requirement in natural language. The agent pipeline plans, generates, verifies, and optimizes IEC 61131-3 Structured Text.
              </p>
              <div className="mt-4 flex flex-wrap gap-3">
                <Button variant="secondary" asChild>
                  <Link href="/new-project">
                    <Plus />
                    New PLC Project
                  </Link>
                </Button>
                <Button variant="ghost" className="text-background hover:bg-background/10" asChild>
                  <Link href="/benchmark">Run benchmark suite</Link>
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[2fr_1fr]">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Recent projects</CardTitle>
              <CardDescription>Last 5 sessions sorted by activity</CardDescription>
            </div>
            <Button variant="ghost" asChild>
              <Link href="/history">
                View all
                <ArrowRight />
              </Link>
            </Button>
          </CardHeader>
          <div className="overflow-x-auto">
            <Table>
              <THead>
                <TR>
                  <TH>Project</TH>
                  <TH>Domain</TH>
                  <TH>Updated</TH>
                  <TH>Iters</TH>
                  <TH>Delta complexity</TH>
                  <TH>Status</TH>
                </TR>
              </THead>
              <TBody>
                {data.projects.map((project) => (
                  <TR key={project.id}>
                    <TD>
                      <div className="font-medium">{project.name}</div>
                      <div className="font-mono text-xs text-muted-foreground">{project.id}</div>
                    </TD>
                    <TD>{project.domain}</TD>
                    <TD className="font-mono text-xs">{project.updated}</TD>
                    <TD>{project.iterations}</TD>
                    <TD>{project.delta}</TD>
                    <TD>
                      <StatusBadge status={project.status as Status} />
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </div>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Checks-passed yield by domain</CardTitle>
            <CardDescription>First-pass rate of passing validation checks</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {data.domainYield.map((domain) => (
              <div key={domain.domain}>
                <div className="mb-1 flex justify-between text-sm">
                  <span>{domain.domain}</span>
                  <span className="text-muted-foreground">{domain.value}%</span>
                </div>
                <Progress value={domain.value} />
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

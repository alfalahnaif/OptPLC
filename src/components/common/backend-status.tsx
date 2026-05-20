"use client";

import { AlertCircle, CheckCircle2, Database, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getApiBaseUrl, getHealth, isMockApiEnabled, useApiResource } from "@/lib/api-client";

export function BackendStatus() {
  const resource = useApiResource(getHealth, []);
  const mockMode = isMockApiEnabled();

  let content = (
    <div className="flex items-center gap-3 text-sm text-muted-foreground">
      <Loader2 className="size-4 animate-spin" />
      Checking backend status
    </div>
  );

  if (resource.state === "ready" && resource.data) {
    content = (
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="grid size-9 place-items-center rounded-md bg-muted">
            {mockMode ? <Database className="size-4" /> : <CheckCircle2 className="size-4 text-emerald-700" />}
          </span>
          <div>
            <div className="text-sm font-medium">{mockMode ? "Mock API mode" : "FastAPI backend online"}</div>
            <div className="font-mono text-xs text-muted-foreground">
              {mockMode ? "NEXT_PUBLIC_USE_MOCK_API=true" : getApiBaseUrl()}
            </div>
          </div>
        </div>
        <Badge tone={mockMode ? "info" : "success"} dot>
          {resource.data.status}
        </Badge>
      </div>
    );
  }

  if (resource.state === "error") {
    content = (
      <div className="flex items-start gap-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300">
        <AlertCircle className="mt-0.5 size-4 shrink-0" />
        <div>
          <div className="font-medium">Backend offline</div>
          <div className="mt-1 text-xs">{resource.error?.message ?? "FastAPI did not respond."}</div>
        </div>
      </div>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Backend connection</CardTitle>
      </CardHeader>
      <CardContent>{content}</CardContent>
    </Card>
  );
}


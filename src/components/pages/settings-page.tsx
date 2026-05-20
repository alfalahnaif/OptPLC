"use client";

import { Save, Settings } from "lucide-react";

import { BackendStatus } from "@/components/common/backend-status";
import { PageStateGate, type PageState } from "@/components/common/page-state";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { getSettingsData, useApiResource } from "@/lib/api-client";

export function SettingsPage({ state }: { state?: PageState } = {}) {
  const resource = useApiResource(getSettingsData, []);
  const effectiveState = state ?? resource.state;
  const data = resource.data;
  const stateView =
    effectiveState !== "ready" || !data ? (
      <PageStateGate
        state={effectiveState === "ready" ? "loading" : effectiveState}
        loading={{ title: "Loading settings", description: "Preparing frontend-only configuration defaults." }}
        empty={{ title: "No settings available", description: "Configuration groups will appear here when provided." }}
        error={{ title: "Settings unavailable", description: "The mock settings data could not be rendered." }}
      />
    ) : null;

  return (
    <>
      <PageHeader
        eyebrow="System"
        title="Settings"
        description="Frontend-only configuration mock for model routing, verification engines, and optimization limits."
        actions={<Button><Save /> Save settings</Button>}
      />
      {stateView ?? (data ? (
        <>
      <div className="mb-5">
        <BackendStatus />
      </div>
      <div className="grid gap-5 xl:grid-cols-3">
        {data.settingsGroups.map((group) => (
          <Card key={group.title}>
            <CardHeader><CardTitle className="flex items-center gap-2"><Settings className="size-4 text-primary" /> {group.title}</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              {group.rows.map(([label, value]) => (
                <label className="block" key={label}>
                  <span className="text-sm font-medium">{label}</span>
                  <Input className="mt-2" defaultValue={value} />
                </label>
              ))}
            </CardContent>
          </Card>
        ))}
      </div>
      <Card className="mt-5">
        <CardHeader><CardTitle>Interface preferences</CardTitle></CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-3">
          {["Compact tables", "Show raw JSON panels", "Use strict IEC wording"].map((item) => (
            <label className="flex items-center justify-between rounded-md border bg-muted/30 p-3 text-sm" key={item}>
              <span>{item}</span>
              <input type="checkbox" defaultChecked className="size-4 accent-blue-600" />
            </label>
          ))}
        </CardContent>
      </Card>
        </>
      ) : null)}
    </>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { pipelineSteps } from "@/lib/mock-data";
import { ACTIVE_PROJECT_ID, projectPath, type ProjectRouteSegment } from "@/lib/api-client";
import { cn } from "@/lib/utils";

export function PipelineStrip({ projectId = ACTIVE_PROJECT_ID }: { projectId?: string }) {
  const pathname = usePathname();

  return (
    <div className="mb-6 overflow-x-auto rounded-lg border bg-card p-3">
      <div className="flex min-w-max items-center gap-2">
        <span className="px-2 font-mono text-[11px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
          Pipeline
        </span>
        {pipelineSteps.map((step, index) => {
          const segment = step.href.replace("/", "") as ProjectRouteSegment;
          const href = projectPath(projectId, segment);
          const active = pathname === href || pathname === step.href;
          return (
            <div className="flex items-center gap-2" key={step.href}>
              <Link
                href={href}
                className={cn(
                  "rounded-md px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
                  active && "bg-foreground text-background hover:bg-foreground hover:text-background"
                )}
              >
                <span className="font-mono">{step.id}</span> {step.title}
              </Link>
              {index < pipelineSteps.length - 1 ? <span className="h-px w-4 bg-border" /> : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

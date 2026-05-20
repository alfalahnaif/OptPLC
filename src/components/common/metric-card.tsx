import { LucideIcon, TrendingUp } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const toneClasses: Record<string, string> = {
  primary: "bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300",
  success: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300",
  info: "bg-sky-50 text-sky-700 dark:bg-sky-950/40 dark:text-sky-300",
  warning: "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300"
};

export function MetricCard({
  label,
  value,
  detail,
  delta,
  icon: Icon,
  tone = "primary"
}: {
  label: string;
  value: string;
  detail?: string;
  delta?: string;
  icon?: LucideIcon;
  tone?: string;
}) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">{label}</div>
          {Icon ? (
            <span className={cn("grid size-8 place-items-center rounded-md", toneClasses[tone] ?? toneClasses.primary)}>
              <Icon className="size-4" />
            </span>
          ) : null}
        </div>
        <div className="mt-5 flex items-baseline gap-2">
          <div className="text-3xl font-semibold tracking-tight">{value}</div>
        </div>
        <div className="mt-3 flex items-center justify-between gap-3 text-xs text-muted-foreground">
          {delta ? (
            <span className="inline-flex items-center gap-1 text-emerald-700 dark:text-emerald-300">
              <TrendingUp className="size-3.5" />
              {delta}
            </span>
          ) : null}
          {detail ? <span>{detail}</span> : null}
        </div>
      </CardContent>
    </Card>
  );
}

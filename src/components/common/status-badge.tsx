import { Badge } from "@/components/ui/badge";

export type Status = "optimized" | "verified" | "failed" | "completed" | "healthy" | "passed" | "warning";

const map: Record<Status, { label: string; tone: "success" | "warning" | "danger" | "neutral" | "info" | "primary" }> = {
  optimized: { label: "Optimized", tone: "success" },
  verified: { label: "Verified", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
  completed: { label: "Completed", tone: "success" },
  healthy: { label: "Healthy", tone: "success" },
  passed: { label: "Passed", tone: "success" },
  warning: { label: "Warning", tone: "warning" }
};

export function StatusBadge({ status, label }: { status: Status; label?: string }) {
  const meta = map[status];
  return (
    <Badge tone={meta.tone} dot className="font-mono uppercase tracking-wider">
      {label ?? meta.label}
    </Badge>
  );
}

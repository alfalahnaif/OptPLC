import { Badge } from "@/components/ui/badge";
import type { EvidenceLevel } from "@/lib/api-contracts";

// Evidence ladder L0-L6 (D-003, D-033). Only L4 and above may be called verified.
const levels: Record<EvidenceLevel, { rank: number; label: string }> = {
  GENERATED: { rank: 0, label: "Generated" },
  COMPILES: { rank: 1, label: "Compiles" },
  STATIC_RULES_PASSED: { rank: 2, label: "Static rules passed" },
  SIMULATION_TESTED: { rank: 3, label: "Simulation tested" },
  PROPERTIES_PROVEN: { rank: 4, label: "Properties proven" },
  HIL_PASSED: { rank: 5, label: "HIL passed" },
  ENGINEER_APPROVED: { rank: 6, label: "Engineer approved" }
};

export function evidenceLabel(level: EvidenceLevel | undefined) {
  const meta = levels[level ?? "GENERATED"];
  return `L${meta.rank} · ${meta.label}`;
}

export function EvidenceBadge({ level }: { level?: EvidenceLevel }) {
  const rank = levels[level ?? "GENERATED"].rank;
  return (
    <Badge tone={rank >= 4 ? "success" : rank >= 1 ? "info" : "neutral"} dot>
      Evidence {evidenceLabel(level)}
    </Badge>
  );
}

export function SafetyScopeNotice() {
  return (
    <div
      role="note"
      className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200"
    >
      <strong>Safety functions are out of scope.</strong> Emergency stop, guards, and safety interlocks must run on a
      certified safety PLC or relay designed under IEC 62061 or ISO 13849. Passing these checks is not formal verification.
    </div>
  );
}

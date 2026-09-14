"use client";

import { Badge } from "@/components/ui/badge";
import { Cpu, Sparkles } from "lucide-react";

export function PlanningModeBadge() {
  const mode = process.env.NEXT_PUBLIC_PLANNING_MODE ?? "rule_based";

  if (mode === "llm") {
    return (
      <Badge tone="primary" className="inline-flex items-center gap-1 text-xs">
        <Sparkles className="h-3 w-3" />
        LLM Mode
      </Badge>
    );
  }

  return (
    <Badge tone="neutral" className="inline-flex items-center gap-1 text-xs">
      <Cpu className="h-3 w-3" />
      Rule-Based
    </Badge>
  );
}


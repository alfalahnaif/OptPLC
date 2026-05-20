"use client";

import { Badge } from "@/components/ui/badge";
import { isMockApiEnabled } from "@/lib/api-client";

export function PlanningModeBadge() {
  const mockMode = isMockApiEnabled();

  return (
    <Badge tone={mockMode ? "info" : "success"} dot>
      {mockMode ? "Mock Planning Mode" : "Real Backend Planning Agent"}
    </Badge>
  );
}


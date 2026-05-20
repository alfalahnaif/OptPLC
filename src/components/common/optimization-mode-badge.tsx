"use client";

import { Badge } from "@/components/ui/badge";
import { isMockApiEnabled } from "@/lib/api-client";

export function OptimizationModeBadge() {
  const mockMode = isMockApiEnabled();

  return (
    <Badge tone={mockMode ? "info" : "success"} dot>
      {mockMode ? "Mock Optimizer" : "Real Static Optimizer"}
    </Badge>
  );
}

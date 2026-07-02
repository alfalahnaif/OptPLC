"use client";

import { Badge } from "@/components/ui/badge";
import { isMockApiEnabled } from "@/lib/api-client";

export function MetricsModeBadge() {
  const mockMode = isMockApiEnabled();
  return (
    <Badge tone={mockMode ? "info" : "success"} dot>
      {mockMode ? "Mock Metrics" : "Real Backend MetricsReport"}
    </Badge>
  );
}

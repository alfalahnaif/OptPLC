"use client";

import { Badge } from "@/components/ui/badge";
import { isMockApiEnabled } from "@/lib/api-client";

export function BenchmarkModeBadge() {
  const mockMode = isMockApiEnabled();
  return (
    <Badge tone={mockMode ? "info" : "success"} dot>
      {mockMode ? "Mock Benchmark" : "Real Backend Benchmark"}
    </Badge>
  );
}

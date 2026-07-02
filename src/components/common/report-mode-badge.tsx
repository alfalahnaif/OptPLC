"use client";

import { Badge } from "@/components/ui/badge";
import { isMockApiEnabled } from "@/lib/api-client";

export function ReportModeBadge() {
  const mockMode = isMockApiEnabled();
  return (
    <Badge tone={mockMode ? "info" : "success"} dot>
      {mockMode ? "Mock Final Report" : "Real Backend FinalReport"}
    </Badge>
  );
}

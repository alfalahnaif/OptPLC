"use client";

import { Badge } from "@/components/ui/badge";
import { isMockApiEnabled } from "@/lib/api-client";

export function DebuggingModeBadge() {
  const mockMode = isMockApiEnabled();

  return (
    <Badge tone={mockMode ? "info" : "success"} dot>
      {mockMode ? "Mock Debugger" : "Real Rule-Based Debugger"}
    </Badge>
  );
}

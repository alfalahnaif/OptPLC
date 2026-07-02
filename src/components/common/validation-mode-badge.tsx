"use client";

import { Badge } from "@/components/ui/badge";
import { isMockApiEnabled } from "@/lib/api-client";

export function ValidationModeBadge() {
  return (
    <Badge tone="info">
      {isMockApiEnabled() ? "Mock Validator" : "Real Backend ValidationReport"}
    </Badge>
  );
}

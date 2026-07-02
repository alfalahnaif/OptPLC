"use client";

import { Badge } from "@/components/ui/badge";
import { isMockApiEnabled } from "@/lib/api-client";

export function CodeGenerationModeBadge() {
  const mockMode = isMockApiEnabled();

  return (
    <Badge tone={mockMode ? "info" : "success"} dot>
      {mockMode ? "Mock Code Generator" : "Real Backend CodeArtifact"}
    </Badge>
  );
}

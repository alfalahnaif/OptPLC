"use client";

import { ErrorState } from "@/components/common/page-state";

export default function Error() {
  return <ErrorState title="Project route unavailable" description="The project-scoped mock client failed to render this route." />;
}

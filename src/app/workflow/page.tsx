import { redirect } from "next/navigation";
import { ACTIVE_PROJECT_ID, projectPath } from "@/lib/api-client";

export default function Page() {
  redirect(projectPath(ACTIVE_PROJECT_ID, "workflow"));
}

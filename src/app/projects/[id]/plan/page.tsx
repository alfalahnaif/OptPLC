import { PlanPage } from "@/components/pages/plan-page";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <PlanPage projectId={id} />;
}

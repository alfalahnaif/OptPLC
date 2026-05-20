import { RequirementsPage } from "@/components/pages/requirements-page";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <RequirementsPage projectId={id} />;
}

import { ProjectOverviewPage } from "@/components/pages/project-overview-page";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ProjectOverviewPage projectId={id} />;
}

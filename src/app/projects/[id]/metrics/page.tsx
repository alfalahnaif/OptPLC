import { MetricsPage } from "@/components/pages/metrics-page";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <MetricsPage projectId={id} />;
}

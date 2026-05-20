import { OptimizationPage } from "@/components/pages/optimization-page";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <OptimizationPage projectId={id} />;
}

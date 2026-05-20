import { ReportPage } from "@/components/pages/report-page";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ReportPage projectId={id} />;
}

import { DebuggingPage } from "@/components/pages/debugging-page";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <DebuggingPage projectId={id} />;
}

import { ValidationPage } from "@/components/pages/validation-page";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ValidationPage projectId={id} />;
}

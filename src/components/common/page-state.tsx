import { AlertCircle, Inbox, Loader2, RefreshCw } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export type PageState = "ready" | "loading" | "empty" | "error";

type StateProps = {
  title?: string;
  description?: string;
};

export function LoadingState({
  title = "Loading workspace",
  description = "Preparing the latest mock engineering data."
}: StateProps) {
  return (
    <Card>
      <CardContent className="flex min-h-72 flex-col items-center justify-center text-center">
        <Loader2 className="mb-4 size-9 animate-spin text-primary" />
        <div className="text-base font-semibold">{title}</div>
        <p className="mt-2 max-w-md text-sm text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  );
}

export function EmptyState({
  title = "No mock records available",
  description = "This view is ready for API data, but the current mock set is empty."
}: StateProps) {
  return (
    <Card>
      <CardContent className="flex min-h-72 flex-col items-center justify-center text-center">
        <Inbox className="mb-4 size-9 text-muted-foreground" />
        <div className="text-base font-semibold">{title}</div>
        <p className="mt-2 max-w-md text-sm text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  );
}

export function ErrorState({
  title = "Unable to load mock data",
  description = "The UI can recover once the data source is available."
}: StateProps) {
  return (
    <Alert variant="destructive" className="min-h-32">
      <AlertCircle className="mb-3 size-5" />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>{description}</AlertDescription>
      <Button variant="outline" size="sm" className="mt-4">
        <RefreshCw />
        Retry
      </Button>
    </Alert>
  );
}

export function PageStateGate({
  state = "ready",
  loading,
  empty,
  error
}: {
  state?: PageState;
  loading?: StateProps;
  empty?: StateProps;
  error?: StateProps;
}) {
  if (state === "loading") return <LoadingState {...loading} />;
  if (state === "empty") return <EmptyState {...empty} />;
  if (state === "error") return <ErrorState {...error} />;
  return null;
}

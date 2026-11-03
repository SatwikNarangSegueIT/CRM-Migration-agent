// Public unsubscribe page (link in every marketing e-mail). No sign-in required.
import { useMutation, useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { errorMessage } from "../../api/client";
import { publicApi } from "../../api/portal";
import { AuthLayout } from "../../components/AuthLayout";
import { Alert, Button, Spinner } from "../../components/ui";

export function UnsubscribePage() {
  const { token = "" } = useParams();
  const info = useQuery({
    queryKey: ["unsubscribe", token],
    queryFn: () => publicApi.unsubscribeInfo(token),
    retry: false,
  });
  const unsubscribe = useMutation({ mutationFn: () => publicApi.unsubscribe(token) });
  const done = unsubscribe.isSuccess || info.data?.unsubscribed;
  return (
    <AuthLayout title="E-mail preferences">
      {info.isPending ? (
        <Spinner label="Loading" />
      ) : info.isError ? (
        <Alert tone="error">This link is invalid or has expired.</Alert>
      ) : done ? (
        <Alert tone="success" title="You're unsubscribed">
          {info.data.email} will no longer receive marketing e-mails from {info.data.sender}.
        </Alert>
      ) : (
        <div className="space-y-4">
          <p className="text-sm text-slate-700">
            Stop marketing e-mails from <strong>{info.data.sender}</strong> to{" "}
            <strong>{info.data.email}</strong>?
          </p>
          {unsubscribe.isError && <Alert tone="error">{errorMessage(unsubscribe.error)}</Alert>}
          <Button className="w-full" loading={unsubscribe.isPending} onClick={() => unsubscribe.mutate()}>
            Unsubscribe
          </Button>
          <p className="text-xs text-slate-500">
            You'll still receive messages about your account, cases and invoices.
          </p>
        </div>
      )}
    </AuthLayout>
  );
}

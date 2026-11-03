import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { authApi } from "../../api/auth";
import { errorMessage, fieldError } from "../../api/client";
import { useHashToken } from "../../auth/useHashToken";
import { AuthLayout } from "../../components/AuthLayout";
import { NewPasswordFields } from "../../components/NewPasswordFields";
import { passwordsReady } from "../../lib/password";
import { Alert, Button, Spinner } from "../../components/ui";

export function AcceptInvitationPage() {
  const token = useHashToken();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const invitation = useQuery({
    queryKey: ["invitation", token],
    queryFn: () => authApi.inspectInvitation(token),
    enabled: Boolean(token),
    retry: false,
    staleTime: Infinity,
  });
  const accept = useMutation({ mutationFn: () => authApi.acceptInvitation(token, password) });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    accept.mutate();
  }

  let content;
  if (accept.isSuccess) {
    content = (
      <div className="space-y-4">
        <Alert tone="success">{accept.data.message}</Alert>
        <Link to="/login" className="block text-center text-sm font-medium text-brand-700 hover:underline">
          Go to sign in
        </Link>
      </div>
    );
  } else if (!token || invitation.isError) {
    content = (
      <div className="space-y-4">
        <Alert tone="error">
          {invitation.isError
            ? errorMessage(invitation.error)
            : "This invitation link is invalid or incomplete. Ask your administrator to send a new one."}
        </Alert>
        <Link to="/login" className="block text-center text-sm font-medium text-brand-700 hover:underline">
          Go to sign in
        </Link>
      </div>
    );
  } else if (invitation.isPending) {
    content = <Spinner label="Checking invitation" />;
  } else {
    content = (
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <div className="rounded-md bg-slate-50 px-4 py-3 text-sm">
          <p className="font-medium text-slate-900">{invitation.data.name}</p>
          <p className="text-slate-600">{invitation.data.email}</p>
        </div>
        {accept.isError && !fieldError(accept.error, "password") && (
          <Alert tone="error">{errorMessage(accept.error)}</Alert>
        )}
        <NewPasswordFields
          label="Password"
          password={password}
          confirm={confirm}
          onPassword={setPassword}
          onConfirm={setConfirm}
          serverError={fieldError(accept.error, "password")}
        />
        <Button
          type="submit"
          className="w-full"
          loading={accept.isPending}
          disabled={!passwordsReady(password, confirm)}
        >
          Create account
        </Button>
      </form>
    );
  }

  return (
    <AuthLayout title="Welcome to MigrateCRM" subtitle="Set a password to activate your account.">
      {content}
    </AuthLayout>
  );
}

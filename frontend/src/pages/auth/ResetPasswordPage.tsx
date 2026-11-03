import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { authApi } from "../../api/auth";
import { ApiError, errorMessage, fieldError } from "../../api/client";
import { useHashToken } from "../../auth/useHashToken";
import { AuthLayout } from "../../components/AuthLayout";
import { NewPasswordFields } from "../../components/NewPasswordFields";
import { passwordsReady } from "../../lib/password";
import { Alert, Button } from "../../components/ui";

export function ResetPasswordPage() {
  const token = useHashToken();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const reset = useMutation({ mutationFn: () => authApi.resetPassword(token, password) });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    reset.mutate();
  }

  const invalidLink = !token || (reset.error instanceof ApiError && reset.error.code === "invalid_token");

  return (
    <AuthLayout title="Choose a new password">
      {reset.isSuccess ? (
        <div className="space-y-4">
          <Alert tone="success">{reset.data.message}</Alert>
          <Link to="/login" className="block text-center text-sm font-medium text-brand-700 hover:underline">
            Go to sign in
          </Link>
        </div>
      ) : invalidLink ? (
        <div className="space-y-4">
          <Alert tone="error">
            {reset.error
              ? errorMessage(reset.error)
              : "This link is invalid or incomplete. Request a new one."}
          </Alert>
          <Link
            to="/forgot-password"
            className="block text-center text-sm font-medium text-brand-700 hover:underline"
          >
            Request a new link
          </Link>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          {reset.isError && !fieldError(reset.error, "password") && (
            <Alert tone="error">{errorMessage(reset.error)}</Alert>
          )}
          <NewPasswordFields
            password={password}
            confirm={confirm}
            onPassword={setPassword}
            onConfirm={setConfirm}
            serverError={fieldError(reset.error, "password")}
          />
          <Button
            type="submit"
            className="w-full"
            loading={reset.isPending}
            disabled={!passwordsReady(password, confirm)}
          >
            Set new password
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}

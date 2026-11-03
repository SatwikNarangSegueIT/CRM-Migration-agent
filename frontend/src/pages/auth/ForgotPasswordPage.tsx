import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { authApi } from "../../api/auth";
import { errorMessage } from "../../api/client";
import { AuthLayout } from "../../components/AuthLayout";
import { Alert, Button, TextField } from "../../components/ui";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const request = useMutation({ mutationFn: () => authApi.forgotPassword(email) });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    request.mutate();
  }

  return (
    <AuthLayout title="Reset your password" subtitle="We'll e-mail you a link to choose a new password.">
      {request.isSuccess ? (
        <div className="space-y-4">
          <Alert tone="success">{request.data.message}</Alert>
          <p className="text-sm text-slate-600">The link expires soon and can be used once.</p>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          {request.isError && <Alert tone="error">{errorMessage(request.error)}</Alert>}
          <TextField
            label="E-mail"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Button type="submit" className="w-full" loading={request.isPending} disabled={!email}>
            Send reset link
          </Button>
        </form>
      )}
      <p className="mt-6 text-center text-sm">
        <Link to="/login" className="font-medium text-brand-700 hover:underline">
          Back to sign in
        </Link>
      </p>
    </AuthLayout>
  );
}

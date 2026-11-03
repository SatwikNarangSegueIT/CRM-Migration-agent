import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { authApi } from "../../api/auth";
import { errorMessage } from "../../api/client";
import { useAuth } from "../../auth/context";
import { safeNext } from "../../auth/redirect";
import { AuthLayout } from "../../components/AuthLayout";
import { Alert, Button, TextField } from "../../components/ui";

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { refresh } = useAuth();
  const next = safeNext(params.get("next"));

  const login = useMutation({
    mutationFn: () => authApi.login(email, password),
    onSuccess: async ({ state }) => {
      await refresh();
      const nextParam = `?next=${encodeURIComponent(next)}`;
      if (state === "mfa_required") navigate(`/mfa${nextParam}`, { replace: true });
      else if (state === "mfa_setup_required") navigate(`/mfa/setup${nextParam}`, { replace: true });
      else navigate(next, { replace: true });
    },
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    login.mutate();
  }

  return (
    <AuthLayout title="Sign in" subtitle="Use your work account.">
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {login.isError && <Alert tone="error">{errorMessage(login.error)}</Alert>}
        <TextField
          label="E-mail"
          type="email"
          autoComplete="username"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <Button type="submit" className="w-full" loading={login.isPending} disabled={!email || !password}>
          Sign in
        </Button>
        <p className="text-center text-sm">
          <Link to="/forgot-password" className="font-medium text-brand-700 hover:underline">
            Forgot your password?
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}

import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { authApi, type LoginResult } from "../../api/auth";
import { errorMessage } from "../../api/client";
import { useAuth } from "../../auth/context";
import { safeNext } from "../../auth/redirect";
import { AuthLayout } from "../../components/AuthLayout";
import { Alert, Button, TextField } from "../../components/ui";

type Workspaces = NonNullable<LoginResult["workspaces"]>;

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [choices, setChoices] = useState<Workspaces | null>(null);
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { refresh } = useAuth();
  const next = safeNext(params.get("next"));

  const login = useMutation({
    mutationFn: (workspace?: string) => authApi.login(email, password, workspace),
    onSuccess: async ({ state, workspaces }) => {
      if (state === "choose_workspace") {
        setChoices(workspaces ?? []);
        return;
      }
      await refresh();
      const nextParam = `?next=${encodeURIComponent(next)}`;
      if (state === "mfa_required") navigate(`/mfa${nextParam}`, { replace: true });
      else if (state === "mfa_setup_required") navigate(`/mfa/setup${nextParam}`, { replace: true });
      else navigate(next, { replace: true });
    },
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    login.mutate(undefined);
  }

  if (choices) {
    return (
      <AuthLayout title="Choose a workspace" subtitle={`${email} belongs to more than one firm.`}>
        <div className="space-y-3">
          {login.isError && <Alert tone="error">{errorMessage(login.error)}</Alert>}
          <ul className="space-y-2" aria-label="Workspaces">
            {choices.map((w) => (
              <li key={w.slug}>
                <button
                  type="button"
                  disabled={login.isPending}
                  onClick={() => login.mutate(w.slug)}
                  className="flex w-full items-center justify-between rounded-lg border border-slate-200 px-4 py-3 text-left hover:border-brand-500 hover:bg-brand-50 focus:outline-none focus:ring-2 focus:ring-brand-500 disabled:opacity-60"
                >
                  <span>
                    <span className="block font-medium text-slate-900">{w.name}</span>
                    <span className="block text-xs text-slate-500">{w.slug}</span>
                  </span>
                  <span aria-hidden="true" className="text-slate-400">
                    →
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <button
            type="button"
            onClick={() => setChoices(null)}
            className="w-full text-center text-sm font-medium text-brand-700 hover:underline"
          >
            Use a different account
          </button>
        </div>
      </AuthLayout>
    );
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
        <p className="border-t border-slate-100 pt-4 text-center text-sm text-slate-600">
          New to Meridian CRM?{" "}
          <Link to="/signup" className="font-medium text-brand-700 hover:underline">
            Create a workspace for your firm
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}

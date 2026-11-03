import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { authApi } from "../../api/auth";
import { errorMessage, fieldError } from "../../api/client";
import { useAuth } from "../../auth/context";
import { safeNext } from "../../auth/redirect";
import { AuthLayout } from "../../components/AuthLayout";
import { RecoveryCodes } from "../../components/RecoveryCodes";
import { Alert, Button, Spinner, TextField } from "../../components/ui";

export function MfaSetupPage() {
  const { me, isLoading, refresh, signOut } = useAuth();
  const [code, setCode] = useState("");
  const [codes, setCodes] = useState<string[] | null>(null);
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const next = safeNext(params.get("next"));

  const begin = useMutation({ mutationFn: () => authApi.beginMfaSetup() });
  const enable = useMutation({
    mutationFn: () => authApi.enableMfa(code),
    onSuccess: async (data) => {
      setCodes(data.recovery_codes);
      await refresh();
    },
  });

  if (codes) {
    return (
      <AuthLayout title="Two-step verification is on" subtitle="Keep these recovery codes safe.">
        <RecoveryCodes codes={codes} onDone={() => navigate(next, { replace: true })} />
      </AuthLayout>
    );
  }
  if (isLoading) return <Spinner />;
  if (!me) return <Navigate to="/login" replace />;
  if (me.user.mfa_enabled) {
    return <Navigate to={me.session.mfa_verified ? next : `/mfa?next=${encodeURIComponent(next)}`} replace />;
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    enable.mutate();
  }

  const required = me.session.mfa_setup_required;

  return (
    <AuthLayout
      title="Set up two-step verification"
      subtitle={
        required
          ? "Your organisation requires an authenticator app for staff accounts."
          : "Protect your account with an authenticator app."
      }
    >
      {!begin.data ? (
        <div className="space-y-4">
          <ol className="list-decimal space-y-1 pl-5 text-sm text-slate-700">
            <li>Install an authenticator app (Microsoft Authenticator, Google Authenticator, 1Password…).</li>
            <li>Scan the QR code we show you.</li>
            <li>Enter the 6-digit code from the app to confirm.</li>
          </ol>
          {begin.isError && <Alert tone="error">{errorMessage(begin.error)}</Alert>}
          <Button className="w-full" loading={begin.isPending} onClick={() => begin.mutate()}>
            Show QR code
          </Button>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <div className="flex justify-center">
            <img
              src={begin.data.qr_svg_data_uri}
              alt="QR code for your authenticator app"
              className="h-48 w-48 rounded border border-slate-200"
            />
          </div>
          <details className="text-sm text-slate-600">
            <summary className="cursor-pointer font-medium text-brand-700">
              Can't scan? Enter the key manually
            </summary>
            <p className="mt-2 break-all rounded bg-slate-50 p-2 font-mono text-xs" aria-label="Setup key">
              {begin.data.secret}
            </p>
          </details>
          {enable.isError && !fieldError(enable.error, "code") && (
            <Alert tone="error">{errorMessage(enable.error)}</Alert>
          )}
          <TextField
            label="6-digit code"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
            error={
              fieldError(enable.error, "code") && "That code is not valid. Check your app and try again."
            }
          />
          <Button type="submit" className="w-full" loading={enable.isPending} disabled={code.length !== 6}>
            Turn on two-step verification
          </Button>
        </form>
      )}
      <p className="mt-6 text-center text-sm">
        {required ? (
          <button
            type="button"
            className="text-slate-600 hover:underline"
            onClick={() => void signOut().then(() => navigate("/login", { replace: true }))}
          >
            Cancel and sign out
          </button>
        ) : (
          <button type="button" className="text-slate-600 hover:underline" onClick={() => navigate(next)}>
            Not now
          </button>
        )}
      </p>
    </AuthLayout>
  );
}

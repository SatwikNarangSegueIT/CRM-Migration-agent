import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { authApi } from "../../api/auth";
import { errorMessage, fieldError } from "../../api/client";
import { useAuth } from "../../auth/context";
import { safeNext } from "../../auth/redirect";
import { AuthLayout } from "../../components/AuthLayout";
import { Alert, Button, Spinner, TextField } from "../../components/ui";
import { ME_QUERY_KEY } from "../../queryClient";
import { useQueryClient } from "@tanstack/react-query";

export function MfaVerifyPage() {
  const { me, isLoading, signOut } = useAuth();
  const [code, setCode] = useState("");
  const [useRecovery, setUseRecovery] = useState(false);
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const next = safeNext(params.get("next"));

  const verify = useMutation({
    mutationFn: () => authApi.verifyMfa(code),
    onSuccess: (data) => {
      queryClient.setQueryData(ME_QUERY_KEY, data);
      navigate(next, { replace: true });
    },
  });

  if (isLoading) return <Spinner />;
  if (!me) return <Navigate to="/login" replace />;
  if (me.session.mfa_verified) return <Navigate to={next} replace />;
  if (me.session.mfa_setup_required)
    return <Navigate to={`/mfa/setup?next=${encodeURIComponent(next)}`} replace />;

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    verify.mutate();
  }

  return (
    <AuthLayout
      title="Two-step verification"
      subtitle={
        useRecovery
          ? "Enter one of your saved recovery codes. Each code works once."
          : "Enter the 6-digit code from your authenticator app."
      }
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {verify.isError && !fieldError(verify.error, "code") && (
          <Alert tone="error">{errorMessage(verify.error)}</Alert>
        )}
        {useRecovery ? (
          <TextField
            key="recovery"
            label="Recovery code"
            autoComplete="off"
            placeholder="ABCDE-FGHJK"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            error={fieldError(verify.error, "code") && "That recovery code is not valid."}
            autoFocus
          />
        ) : (
          <TextField
            key="totp"
            label="Authentication code"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            placeholder="123456"
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
            error={
              fieldError(verify.error, "code") && "That code is not valid. Check your app and try again."
            }
            autoFocus
          />
        )}
        <Button
          type="submit"
          className="w-full"
          loading={verify.isPending}
          disabled={useRecovery ? code.trim().length < 10 : code.length !== 6}
        >
          Verify
        </Button>
        <div className="flex items-center justify-between text-sm">
          <button
            type="button"
            className="font-medium text-brand-700 hover:underline"
            onClick={() => {
              setUseRecovery((v) => !v);
              setCode("");
              verify.reset();
            }}
          >
            {useRecovery ? "Use authenticator app" : "Use a recovery code"}
          </button>
          <button
            type="button"
            className="text-slate-600 hover:underline"
            onClick={() => void signOut().then(() => navigate("/login", { replace: true }))}
          >
            Cancel and sign out
          </button>
        </div>
      </form>
    </AuthLayout>
  );
}

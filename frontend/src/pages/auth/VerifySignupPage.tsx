import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { errorMessage } from "../../api/client";
import { signupApi } from "../../api/signup";
import { useAuth } from "../../auth/context";
import { useHashToken } from "../../auth/useHashToken";
import { AuthLayout } from "../../components/AuthLayout";
import { Alert, Spinner } from "../../components/ui";

/** Opened from the verification e-mail: creates the workspace and signs the administrator in. */
export function VerifySignupPage() {
  const token = useHashToken();
  const navigate = useNavigate();
  const { refresh } = useAuth();
  const started = useRef(false);
  const verify = useMutation({
    mutationFn: () => signupApi.verify(token),
    onSuccess: async ({ state }) => {
      await refresh();
      navigate(state === "mfa_setup_required" ? "/mfa/setup?next=%2F" : "/", { replace: true });
    },
  });

  useEffect(() => {
    if (token && !started.current) {
      started.current = true;
      verify.mutate();
    }
  }, [token, verify]);

  if (!token || verify.isError) {
    return (
      <AuthLayout title="Create your workspace">
        <div className="space-y-4">
          <Alert tone="error">
            {verify.error ? errorMessage(verify.error) : "This link is invalid or incomplete."}
          </Alert>
          <Link to="/signup" className="block text-center text-sm font-medium text-brand-700 hover:underline">
            Sign up again
          </Link>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Setting up your workspace" subtitle="This takes a few seconds.">
      <div className="flex flex-col items-center gap-3 py-6 text-sm text-slate-600">
        <Spinner label="Creating your workspace" />
        <p>Installing your firm's apps, layouts and permissions…</p>
      </div>
    </AuthLayout>
  );
}

import type { ReactNode } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { Spinner } from "../components/ui/Spinner";
import { useAuth } from "./context";
import { loginPath, safeNext } from "./redirect";
import { wasSignedOut } from "./signOutFlag";

function FullPageSpinner() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <Spinner label="Loading" />
    </div>
  );
}

/** Signed in with MFA complete; otherwise redirect to sign-in or the MFA step. */
export function RequireAuth({ children }: { children?: ReactNode }) {
  const { me, isLoading } = useAuth();
  const location = useLocation();
  if (isLoading) return <FullPageSpinner />;
  const here = location.pathname + location.search;
  if (!me) return <Navigate to={wasSignedOut() ? "/login" : loginPath(here)} replace />;
  if (!me.session.mfa_verified) {
    const target = me.session.mfa_setup_required ? "/mfa/setup" : "/mfa";
    return <Navigate to={`${target}?next=${encodeURIComponent(here)}`} replace />;
  }
  return <>{children ?? <Outlet />}</>;
}

/** Staff-only area: clients are sent to their portal. */
export function RequireStaff({ children }: { children?: ReactNode }) {
  const { me } = useAuth();
  if (me && !me.user.is_staff) return <Navigate to="/portal" replace />;
  return <>{children ?? <Outlet />}</>;
}

/** Client portal: staff are sent to the CRM. */
export function RequireClient({ children }: { children?: ReactNode }) {
  const { me } = useAuth();
  if (me && me.user.is_staff) return <Navigate to="/" replace />;
  return <>{children ?? <Outlet />}</>;
}

/** Requires a system permission; with a list, any one of them. The server remains the authority. */
export function RequirePermission({
  permission,
  children,
}: {
  permission: string | string[];
  children?: ReactNode;
}) {
  const { can } = useAuth();
  const allowed = (Array.isArray(permission) ? permission : [permission]).some(can);
  if (!allowed) return <Navigate to="/forbidden" replace />;
  return <>{children ?? <Outlet />}</>;
}

/** Pages for signed-out users (login, forgot password): fully signed-in users go home. */
export function RedirectIfAuthenticated({ children }: { children?: ReactNode }) {
  const { me, isLoading } = useAuth();
  const location = useLocation();
  if (isLoading) return <FullPageSpinner />;
  if (me?.session.mfa_verified) {
    const home = me.user.is_staff ? "/" : "/portal";
    const next = safeNext(new URLSearchParams(location.search).get("next"), home);
    return <Navigate to={next} replace />;
  }
  return <>{children ?? <Outlet />}</>;
}

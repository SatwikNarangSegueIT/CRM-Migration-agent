import type { ReactNode } from "react";
import { useAuth } from "./context";

/** Renders children only when the user holds the permission (UI hint only; the server enforces). */
export function Can({
  permission,
  children,
  fallback = null,
}: {
  permission: string;
  children: ReactNode;
  fallback?: ReactNode;
}) {
  const { can } = useAuth();
  return <>{can(permission) ? children : fallback}</>;
}

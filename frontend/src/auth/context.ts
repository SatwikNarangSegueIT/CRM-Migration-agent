import { useQuery } from "@tanstack/react-query";
import { createContext, useContext, useMemo } from "react";
import type { MeResponse } from "../api/auth";
import type { ObjectAccess } from "../api/types";
import { ME_QUERY_KEY } from "../queryClient";
import { fetchMe } from "./me";

export type AuthActions = {
  refresh: () => Promise<MeResponse | null>;
  signOut: () => Promise<void>;
};

const NO_ACCESS: ObjectAccess = {
  read: false,
  create: false,
  edit: false,
  delete: false,
  view_all: false,
  modify_all: false,
};
const FULL_ACCESS: ObjectAccess = {
  read: true,
  create: true,
  edit: true,
  delete: true,
  view_all: true,
  modify_all: true,
};

export type AuthValue = AuthActions & {
  me: MeResponse | null;
  isLoading: boolean;
  isFullyAuthenticated: boolean;
  /** System permission held (System Administrator holds every permission). UI hint only. */
  can: (permission: string) => boolean;
  /** Object permissions of the user's profile. UI hint only; the server enforces sharing. */
  object: (apiName: string) => ObjectAccess;
  /** Any of the setup-related permissions. */
  canSeeSetup: boolean;
};

export const AuthContext = createContext<AuthActions | null>(null);

export const meQueryOptions = {
  queryKey: ME_QUERY_KEY,
  queryFn: ({ signal }: { signal: AbortSignal }) => fetchMe(signal),
  staleTime: 60_000,
} as const;

const SETUP_PERMISSIONS = [
  "view_setup",
  "manage_users",
  "customize_application",
  "manage_profiles_sharing",
  "manage_billing_settings",
  "manage_industry_packs",
  "view_audit_log",
  "manage_portal_users",
];

/**
 * Current user and permission helpers. Each caller subscribes to the cached /auth/me query directly,
 * so it sees updates (e.g. right after sign-in) in the same render as a navigation.
 */
export function useAuth(): AuthValue {
  const actions = useContext(AuthContext);
  if (!actions) throw new Error("useAuth must be used inside <AuthProvider>");
  const query = useQuery(meQueryOptions);
  const me = query.data ?? null;
  return useMemo(() => {
    const system = new Set(me?.system_permissions ?? []);
    const admin = Boolean(me?.is_system_admin);
    const can = (permission: string) => admin || system.has(permission);
    return {
      ...actions,
      me,
      isLoading: query.isPending,
      isFullyAuthenticated: Boolean(me?.session.mfa_verified),
      can,
      object: (apiName: string) => (admin ? FULL_ACCESS : (me?.object_permissions[apiName] ?? NO_ACCESS)),
      canSeeSetup: Boolean(me?.user.is_staff) && SETUP_PERMISSIONS.some(can),
    };
  }, [actions, me, query.isPending]);
}

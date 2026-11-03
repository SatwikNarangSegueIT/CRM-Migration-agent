import { useQuery } from "@tanstack/react-query";
import { createContext, useContext, useMemo } from "react";
import type { MeResponse } from "../api/auth";
import type { Scope } from "../api/types";
import { ME_QUERY_KEY } from "../queryClient";
import { fetchMe } from "./me";

export type AuthActions = {
  refresh: () => Promise<MeResponse | null>;
  signOut: () => Promise<void>;
};

export type AuthValue = AuthActions & {
  me: MeResponse | null;
  isLoading: boolean;
  isFullyAuthenticated: boolean;
  can: (permission: string) => boolean;
  scope: (permission: string) => Scope | null;
};

export const AuthContext = createContext<AuthActions | null>(null);

export const meQueryOptions = {
  queryKey: ME_QUERY_KEY,
  queryFn: ({ signal }: { signal: AbortSignal }) => fetchMe(signal),
  staleTime: 60_000,
} as const;

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
    const permissions = me?.permissions ?? {};
    return {
      ...actions,
      me,
      isLoading: query.isPending,
      isFullyAuthenticated: Boolean(me?.session.mfa_verified),
      can: (permission: string) => permission in permissions,
      scope: (permission: string) => permissions[permission] ?? null,
    };
  }, [actions, me, query.isPending]);
}

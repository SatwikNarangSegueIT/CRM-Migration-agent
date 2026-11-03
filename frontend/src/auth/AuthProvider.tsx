import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo, type ReactNode } from "react";
import { authApi } from "../api/auth";
import { ApiError } from "../api/client";
import { ME_QUERY_KEY } from "../queryClient";
import { AuthContext, meQueryOptions, type AuthActions } from "./context";
import { fetchMe } from "./me";
import { markSignedOut } from "./signOutFlag";

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const query = useQuery(meQueryOptions);

  const refresh = useCallback(
    () =>
      queryClient.fetchQuery({
        queryKey: ME_QUERY_KEY,
        queryFn: ({ signal }) => fetchMe(signal),
        staleTime: 0,
      }),
    [queryClient],
  );

  const signOut = useCallback(async () => {
    markSignedOut(true);
    try {
      await authApi.logout();
    } finally {
      queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== ME_QUERY_KEY[0] });
      queryClient.setQueryData(ME_QUERY_KEY, null);
    }
  }, [queryClient]);

  const actions = useMemo<AuthActions>(() => ({ refresh, signOut }), [refresh, signOut]);

  if (query.isError) {
    return (
      <div
        role="alert"
        className="mx-auto mt-24 max-w-md rounded-lg border border-red-200 bg-white p-6 text-center"
      >
        <h1 className="text-lg font-semibold text-slate-900">Cannot reach MigrateCRM</h1>
        <p className="mt-2 text-sm text-slate-600">
          {query.error instanceof ApiError ? query.error.message : "The server is not responding."}
        </p>
        <button
          type="button"
          onClick={() => void query.refetch()}
          className="mt-4 rounded-md bg-brand-700 px-4 py-2 text-sm font-medium text-white hover:bg-brand-800"
        >
          Try again
        </button>
      </div>
    );
  }

  return <AuthContext.Provider value={actions}>{children}</AuthContext.Provider>;
}

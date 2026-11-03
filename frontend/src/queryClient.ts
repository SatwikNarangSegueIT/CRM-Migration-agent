import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";
import { ApiError } from "./api/client";

export const ME_QUERY_KEY = ["auth", "me"] as const;

/**
 * Session-level errors from any request:
 * - 401 unauthenticated: the session ended -> clear the cached user; route guards send the user to /login.
 * - 403 mfa_required / csrf_failed: session state changed -> refetch /auth/me so guards can react.
 */
function handleSessionError(client: QueryClient, error: unknown): void {
  if (!(error instanceof ApiError)) return;
  if (error.status === 401 && error.code === "unauthenticated") {
    client.setQueryData(ME_QUERY_KEY, null);
  } else if (error.status === 403 && (error.code === "mfa_required" || error.code === "csrf_failed")) {
    void client.invalidateQueries({ queryKey: ME_QUERY_KEY });
  }
}

export function createQueryClient(): QueryClient {
  const client: QueryClient = new QueryClient({
    queryCache: new QueryCache({ onError: (error) => handleSessionError(client, error) }),
    mutationCache: new MutationCache({ onError: (error) => handleSessionError(client, error) }),
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        // Do not retry client errors (4xx); retry network/server errors twice.
        retry: (failureCount, error) =>
          !(error instanceof ApiError && error.status >= 400 && error.status < 500) && failureCount < 2,
      },
    },
  });
  return client;
}

import { apiRequest } from "./client";

export type CheckStatus = "ok" | "error";

export type LiveStatus = { status: "ok"; app: string; environment: string };
export type ReadyStatus = { status: CheckStatus; checks: Record<string, CheckStatus> };

export function getLive(signal?: AbortSignal): Promise<LiveStatus> {
  return apiRequest<LiveStatus>("/health/live", { signal });
}

/** Readiness returns 503 with a body when a dependency is down; that is data, not an exception. */
export function getReady(signal?: AbortSignal): Promise<ReadyStatus> {
  return apiRequest<ReadyStatus>("/health/ready", { signal, acceptStatuses: [503] });
}

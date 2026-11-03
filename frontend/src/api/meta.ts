import { apiRequest } from "./client";
import type { Role, Scope } from "./types";

export type RoleInfo = { value: Role; label: string; is_staff: boolean; permissions: Record<string, Scope> };

export const metaApi = {
  roles: (signal?: AbortSignal) => apiRequest<RoleInfo[]>("/meta/roles", { signal }),
};

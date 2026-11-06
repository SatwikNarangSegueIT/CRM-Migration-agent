import { apiRequest, toQueryString } from "./client";
import type { MessageResponse, Page } from "./types";

export type User = {
  id: string;
  email: string;
  name: string;
  profile: { id: string; name: string; is_portal: boolean };
  role: { id: string; name: string } | null;
  is_active: boolean;
  title: string | null;
  phone: string | null;
  mara_number: string | null;
  mfa_enabled: boolean;
  last_login_at: string | null;
  locked_until: string | null;
  created_at: string;
  updated_at: string;
  has_password: boolean;
};

export type UserListParams = {
  page?: number;
  page_size?: number;
  q?: string;
  profile_id?: string;
  role_id?: string;
  is_active?: boolean;
};

export type UserCreateInput = {
  email: string;
  name: string;
  profile_id: string;
  role_id: string | null;
  title: string | null;
  phone: string | null;
  mara_number: string | null;
};

export type UserUpdateInput = {
  updated_at: string;
  name?: string;
  profile_id?: string;
  role_id?: string | null;
  title?: string | null;
  phone?: string | null;
  mara_number?: string | null;
  is_active?: boolean;
};

export function isLocked(user: Pick<User, "locked_until">, now: Date = new Date()): boolean {
  return user.locked_until !== null && new Date(user.locked_until) > now;
}

export const usersApi = {
  list: (params: UserListParams, signal?: AbortSignal) =>
    apiRequest<Page<User>>(`/admin/users${toQueryString(params)}`, { signal }),
  get: (id: string, signal?: AbortSignal) => apiRequest<User>(`/admin/users/${id}`, { signal }),
  create: (body: UserCreateInput) => apiRequest<User>("/admin/users", { method: "POST", body }),
  update: (id: string, body: UserUpdateInput) =>
    apiRequest<User>(`/admin/users/${id}`, { method: "PATCH", body }),
  resendInvitation: (id: string) =>
    apiRequest<MessageResponse>(`/admin/users/${id}/resend-invitation`, { method: "POST" }),
  resetMfa: (id: string) => apiRequest<User>(`/admin/users/${id}/reset-mfa`, { method: "POST" }),
  unlock: (id: string) => apiRequest<User>(`/admin/users/${id}/unlock`, { method: "POST" }),
  revokeSessions: (id: string) =>
    apiRequest<MessageResponse>(`/admin/users/${id}/revoke-sessions`, { method: "POST" }),
  /** Delete a user: their records move to `transferTo` (default: you) and their e-mail is released. */
  remove: (id: string, transferTo?: string) =>
    apiRequest<MessageResponse>(
      `/admin/users/${id}${transferTo ? `?transfer_to=${encodeURIComponent(transferTo)}` : ""}`,
      { method: "DELETE" },
    ),
  /** Active staff, for choosing who takes over a deleted user's records. */
  staff: (signal?: AbortSignal) =>
    apiRequest<{ id: string; name: string; email: string }[]>("/meta/users?limit=50", { signal }),
};

import { apiRequest, toQueryString } from "./client";
import type { Page } from "./types";

export type AuditLog = {
  id: string;
  created_at: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  summary: string;
  changes: Record<string, unknown> | null;
  ip_address: string | null;
  user_agent: string | null;
  request_id: string | null;
  actor: { id: string; name: string; email: string } | null;
};

export type AuditLogParams = {
  page?: number;
  page_size?: number;
  user_id?: string;
  action?: string;
  entity_type?: string;
  entity_id?: string;
  date_from?: string;
  date_to?: string;
};

export const AUDIT_ACTIONS = [
  "CREATE",
  "UPDATE",
  "DELETE",
  "LOGIN",
  "LOGIN_FAILED",
  "LOGOUT",
  "ACCOUNT_LOCKED",
  "MFA_ENABLED",
  "MFA_FAILED",
  "MFA_RESET",
  "RECOVERY_CODE_USED",
  "PASSWORD_CHANGED",
  "PASSWORD_RESET_REQUESTED",
  "PASSWORD_RESET",
  "INVITATION_SENT",
  "INVITATION_ACCEPTED",
  "SESSIONS_REVOKED",
  "UNLOCK",
  "EXPORT",
  "DOWNLOAD",
] as const;

export const auditApi = {
  list: (params: AuditLogParams, signal?: AbortSignal) =>
    apiRequest<Page<AuditLog>>(`/admin/audit-logs${toQueryString(params)}`, { signal }),
};

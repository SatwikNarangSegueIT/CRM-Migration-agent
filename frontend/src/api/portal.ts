import { apiRequest, toQueryString } from "./client";
import type { FieldDescribe, LayoutSection, RecordData, RecordPage } from "./types";

export type PortalMe = {
  contact: { id: string; name: string; email: string | null; phone: string | null } | null;
  account: { id: string; name: string } | null;
  objects: { api_name: string; label: string; plural_label: string; icon: string; can_create: boolean }[];
  counts: Record<string, number>;
  branding: { name?: string; primary_color?: string };
};

export type PortalRecord = RecordData & {
  actions: { name: string; label: string }[];
  timeline: { note?: RecordData[]; file?: RecordData[] };
  related: { object: string; label: string; columns: string[]; items: RecordData[] }[];
};

/** Portal-safe object description (field labels/types, layout); field-level security applied. */
export type PortalDescribe = {
  api_name: string;
  label: string;
  plural_label: string;
  icon: string;
  color: string;
  name_label: string;
  fields: Record<string, FieldDescribe>;
  page_layout: LayoutSection[];
  compact_layout: string[];
  list_columns: string[];
  path_field: string | null;
};

export const portalApi = {
  describe: (object: string, signal?: AbortSignal) =>
    apiRequest<PortalDescribe>(`/portal/objects/${object}/describe`, { signal }),
  me: (signal?: AbortSignal) => apiRequest<PortalMe>("/portal/me", { signal }),
  list: (object: string, q?: string, cursor?: string | null, signal?: AbortSignal) =>
    apiRequest<RecordPage>(`/portal/objects/${object}/records${toQueryString({ q, cursor })}`, { signal }),
  get: (object: string, id: string, signal?: AbortSignal) =>
    apiRequest<PortalRecord>(`/portal/objects/${object}/records/${id}`, { signal }),
  createCase: (body: { subject: string; description?: string; priority?: string; type?: string }) =>
    apiRequest<RecordData>("/portal/cases", { method: "POST", body }),
  comment: (object: string, id: string, body: string) =>
    apiRequest<RecordData>(`/portal/objects/${object}/records/${id}/comments`, {
      method: "POST",
      body: { body },
    }),
  action: (object: string, id: string, name: string, payload: Record<string, unknown>) =>
    apiRequest<RecordData>(`/portal/objects/${object}/records/${id}/actions/${name}`, {
      method: "POST",
      body: payload,
    }),
};

export const publicApi = {
  branding: () =>
    apiRequest<{ name: string; primary_color: string; logo_url: string | null }>("/public/branding"),
  unsubscribeInfo: (token: string) =>
    apiRequest<{ email: string; unsubscribed: boolean; sender: string }>(`/public/unsubscribe/${token}`),
  unsubscribe: (token: string) =>
    apiRequest<{ unsubscribed: boolean }>(`/public/unsubscribe/${token}`, { method: "POST" }),
};

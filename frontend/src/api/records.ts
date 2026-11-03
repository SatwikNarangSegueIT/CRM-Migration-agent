import { apiRequest, readCookie, CSRF_COOKIE, CSRF_HEADER, API_BASE, toApiError, toQueryString } from "./client";
import type {
  AppInfo,
  FilterNode,
  ListViewDetail,
  ObjectDescribe,
  ObjectSummary,
  RecordData,
  RecordPage,
  SortSpec,
} from "./types";

export type QueryBody = {
  filters?: FilterNode | null;
  columns?: string[] | null;
  sort?: SortSpec[] | null;
  scope?: "mine" | "all" | "team" | "queue";
  search?: string | null;
  cursor?: string | null;
  limit?: number;
  view_id?: string | null;
  deleted?: boolean;
};

export type ListViewInput = {
  name: string;
  visibility: "private" | "public" | "shared";
  shared_profile_ids?: string[];
  shared_role_ids?: string[];
  scope: "mine" | "all" | "team" | "queue";
  columns: string[];
  filters: FilterNode | Record<string, never>;
  sort: SortSpec[];
  kanban_field?: string | null;
};

export type KanbanColumn = {
  value: string;
  label: string;
  color: string | null;
  total: number;
  amount: number | null;
  items: RecordData[];
};

export type HistoryEntry = {
  id: string;
  field: string;
  field_label: string;
  old_value: unknown;
  new_value: unknown;
  changed_by: string | null;
  changed_at: string;
};

export type SearchGroup = {
  object: string;
  label: string;
  icon: string;
  color: string;
  total: number;
  columns: string[];
  items: RecordData[];
};

export type RecentItem = {
  id: string;
  name: string;
  object: string;
  object_label: string;
  icon: string;
  color: string;
  viewed_at: string;
};

export type Notification = {
  id: string;
  title: string;
  body: string | null;
  link: string | null;
  read: boolean;
  created_at: string;
};

export type LookupOption = { id: string; name: string; detail: unknown };
export type UserOption = { id: string; name: string; email: string; title: string | null };

const o = (api: string) => `/objects/${encodeURIComponent(api)}`;

export const metaApi = {
  objects: (signal?: AbortSignal) => apiRequest<ObjectSummary[]>("/meta/objects", { signal }),
  object: (api: string, signal?: AbortSignal) => apiRequest<ObjectDescribe>(`/meta/objects/${api}`, { signal }),
  apps: (signal?: AbortSignal) => apiRequest<AppInfo[]>("/meta/apps", { signal }),
  users: (q: string, signal?: AbortSignal) =>
    apiRequest<UserOption[]>(`/meta/users${toQueryString({ q })}`, { signal }),
  queues: (object: string, signal?: AbortSignal) =>
    apiRequest<{ id: string; name: string }[]>(`/meta/queues${toQueryString({ object_api_name: object })}`, {
      signal,
    }),
  settings: (signal?: AbortSignal) =>
    apiRequest<{ branding?: { name?: string; primary_color?: string }; locale?: Record<string, string> }>(
      "/meta/settings",
      { signal },
    ),
};

export const recordsApi = {
  query: (api: string, body: QueryBody, signal?: AbortSignal) =>
    apiRequest<RecordPage>(`${o(api)}/records/query`, { method: "POST", body, signal }),
  get: (api: string, id: string, signal?: AbortSignal, track = true) =>
    apiRequest<RecordData>(`${o(api)}/records/${id}${track ? "" : "?track=false"}`, { signal }),
  create: (api: string, body: { name?: string; fields: Record<string, unknown>; owner_id?: string; queue_id?: string }) =>
    apiRequest<RecordData>(`${o(api)}/records`, { method: "POST", body }),
  update: (api: string, id: string, body: { version: number; name?: string; fields: Record<string, unknown> }) =>
    apiRequest<RecordData>(`${o(api)}/records/${id}`, { method: "PATCH", body }),
  remove: (api: string, id: string) => apiRequest<void>(`${o(api)}/records/${id}`, { method: "DELETE" }),
  restore: (api: string, id: string) =>
    apiRequest<RecordData>(`${o(api)}/records/${id}/restore`, { method: "POST" }),
  changeOwner: (api: string, id: string, body: { owner_id?: string; queue_id?: string }) =>
    apiRequest<RecordData>(`${o(api)}/records/${id}/change-owner`, { method: "POST", body }),
  bulk: (
    api: string,
    body: { ids: string[]; operation: "update" | "change_owner" | "delete"; values?: Record<string, unknown>; owner_id?: string },
  ) =>
    apiRequest<{ succeeded: number; failed: number; results: { id: string; ok: boolean; error?: string }[] }>(
      `${o(api)}/records/bulk`,
      { method: "POST", body },
    ),
  related: (api: string, id: string, child: string, field: string, limit = 10, cursor?: string | null, signal?: AbortSignal) =>
    apiRequest<RecordPage>(
      `${o(api)}/records/${id}/related/${child}/${field}${toQueryString({ limit, cursor })}`,
      { signal },
    ),
  activities: (api: string, id: string, signal?: AbortSignal) =>
    apiRequest<Record<string, RecordData[]>>(`${o(api)}/records/${id}/activities`, { signal }),
  history: (api: string, id: string, signal?: AbortSignal) =>
    apiRequest<HistoryEntry[]>(`${o(api)}/records/${id}/history`, { signal }),
  action: (api: string, id: string, name: string, payload: Record<string, unknown> = {}) =>
    apiRequest<Record<string, unknown>>(`${o(api)}/records/${id}/actions/${name}`, { method: "POST", body: payload }),
  lookup: (api: string, q: string, signal?: AbortSignal) =>
    apiRequest<LookupOption[]>(`${o(api)}/lookup${toQueryString({ q })}`, { signal }),
  kanban: (api: string, field: string, viewId: string | null, q: string, signal?: AbortSignal) =>
    apiRequest<{ field: string; columns: KanbanColumn[] }>(
      `${o(api)}/kanban${toQueryString({ field, view_id: viewId, q })}`,
      { signal },
    ),
  listViews: (api: string, signal?: AbortSignal) =>
    apiRequest<{ default_view_id: string | null; views: ListViewDetail[] }>(`${o(api)}/list-views`, { signal }),
  createView: (api: string, body: ListViewInput) =>
    apiRequest<ListViewDetail>(`${o(api)}/list-views`, { method: "POST", body }),
  updateView: (api: string, id: string, body: ListViewInput) =>
    apiRequest<ListViewDetail>(`${o(api)}/list-views/${id}`, { method: "PUT", body }),
  deleteView: (api: string, id: string) => apiRequest<void>(`${o(api)}/list-views/${id}`, { method: "DELETE" }),
  pinView: (api: string, id: string) =>
    apiRequest<{ default_view_id: string }>(`${o(api)}/list-views/${id}/pin`, { method: "POST" }),
  shares: (api: string, id: string, signal?: AbortSignal) =>
    apiRequest<{ id: string; principal_type: string; principal_id: string; access: string }[]>(
      `${o(api)}/records/${id}/shares`,
      { signal },
    ),
  addShare: (api: string, id: string, body: { principal_type: string; principal_id: string; access: string }) =>
    apiRequest<unknown>(`${o(api)}/records/${id}/shares`, { method: "POST", body }),
  removeShare: (api: string, id: string, shareId: string) =>
    apiRequest<void>(`${o(api)}/records/${id}/shares/${shareId}`, { method: "DELETE" }),
};

export const workspaceApi = {
  search: (q: string, signal?: AbortSignal, limit = 5) =>
    apiRequest<{ query: string; groups: SearchGroup[] }>(`/search${toQueryString({ q, limit })}`, { signal }),
  recent: (signal?: AbortSignal, limit = 15) =>
    apiRequest<RecentItem[]>(`/me/recent${toQueryString({ limit })}`, { signal }),
  recycleBin: (signal?: AbortSignal) =>
    apiRequest<
      { id: string; name: string; object: string; object_label: string; deleted_at: string; purge_at: string }[]
    >("/recycle-bin", { signal }),
  notifications: (signal?: AbortSignal) =>
    apiRequest<{ unread: number; items: Notification[] }>("/me/notifications", { signal }),
  readNotification: (id: string) => apiRequest<void>(`/me/notifications/${id}/read`, { method: "POST" }),
  readAll: () => apiRequest<void>("/me/notifications/read-all", { method: "POST" }),
  preferences: (signal?: AbortSignal) => apiRequest<Record<string, unknown>>("/me/preferences", { signal }),
  savePreferences: (data: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>("/me/preferences", { method: "PATCH", body: { data } }),
  calendar: (start: string, end: string, mine: boolean, signal?: AbortSignal) =>
    apiRequest<{ events: RecordData[]; tasks: RecordData[] }>(`/calendar${toQueryString({ start, end, mine })}`, {
      signal,
    }),
};

/** Raw-body upload (file name in a header) so no multipart parser is needed. */
export async function uploadFile(
  file: File,
  opts: { relatedTo?: string; isPublic?: boolean; path?: string } = {},
): Promise<RecordData> {
  const headers: Record<string, string> = {
    "Content-Type": file.type || "application/octet-stream",
    "X-File-Name": encodeURIComponent(file.name).replace(/%20/g, " ").replace(/%[0-9A-F]{2}/g, "_"),
    Accept: "application/json",
  };
  const csrf = readCookie(CSRF_COOKIE);
  if (csrf) headers[CSRF_HEADER] = csrf;
  const path = opts.path ?? `/files${toQueryString({ related_to: opts.relatedTo, is_public: opts.isPublic })}`;
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers,
    body: file,
    credentials: "same-origin",
  });
  if (!response.ok) throw await toApiError(response);
  return (await response.json()) as RecordData;
}

export function fileUrl(recordId: string, inline = false, portal = false): string {
  return `${API_BASE}${portal ? "/portal" : ""}/files/${recordId}/content${inline ? "?inline=true" : ""}`;
}

/** POST that returns a file (CSV export); triggers a browser download. */
export async function downloadPost(path: string, body: unknown, fallbackName: string): Promise<void> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const csrf = readCookie(CSRF_COOKIE);
  if (csrf) headers[CSRF_HEADER] = csrf;
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    credentials: "same-origin",
  });
  if (!response.ok) throw await toApiError(response);
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = /filename="([^"]+)"/.exec(disposition);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = match?.[1] ?? fallbackName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

import { apiRequest, toQueryString } from "./client";
import type { FieldDescribe, LayoutSection, ObjectAccess } from "./types";

export type CatalogItem = { value: string; label: string };
export type Catalog = {
  system_permissions: CatalogItem[];
  objects: { api_name: string; label: string; plural: string; app: string; default_sharing: string }[];
  sharing_access: string[];
  field_access: string[];
};

export type ProfileSummary = {
  id: string;
  key: string | null;
  name: string;
  description: string | null;
  is_locked: boolean;
  is_portal: boolean;
  user_count: number;
  created_at: string;
  updated_at: string;
};

export type ProfileDetail = ProfileSummary & {
  system_permissions: string[];
  object_permissions: (ObjectAccess & { object_api_name: string })[];
  field_permissions: {
    object_api_name: string;
    field_api_name: string;
    access: "hidden" | "read" | "edit";
  }[];
};

export type RoleInfo = {
  id: string;
  key: string | null;
  name: string;
  description: string | null;
  parent_id: string | null;
  depth: number;
  user_count: number;
};

export type SharingDefault = {
  object_api_name: string;
  access: string;
  grant_access_using_hierarchy: boolean;
};

export type Group = {
  id: string;
  name: string;
  description: string | null;
  user_ids: string[];
  roles: { role_id: string; include_subordinates: boolean }[];
};

export type Queue = {
  id: string;
  name: string;
  email: string | null;
  object_api_names: string[];
  user_ids: string[];
};

export type SharingRule = {
  id: string;
  object_api_name: string;
  name: string;
  description: string | null;
  rule_type: "owner" | "criteria";
  source_type: string | null;
  source_id: string | null;
  criteria: { logic: "and" | "or"; conditions: { field: string; op: string; value: unknown }[] } | null;
  target_type: string;
  target_id: string;
  access: "read" | "read_write";
};

export type SetupObjectSummary = {
  api_name: string;
  label: string;
  plural_label: string;
  icon: string;
  color: string;
  is_custom: boolean;
  pack_key: string | null;
  description: string | null;
  field_count: number;
  updated_at: string;
};

export type SetupObject = Omit<SetupObjectSummary, "field_count"> & {
  id: string;
  name_field_type: "text" | "auto_number";
  name_label: string;
  name_format: string | null;
  track_history: boolean;
  allow_activities: boolean;
  allow_files: boolean;
  allow_notes: boolean;
  searchable: boolean;
  allow_reports: boolean;
  show_in_portal: boolean;
  allow_queues: boolean;
  is_detail_only: boolean;
  page_layout: LayoutSection[];
  compact_layout: string[];
  related_lists: { object: string; field: string; label: string; columns: string[] }[];
  list_columns: string[];
  fields: FieldDescribe[];
  deleted_fields: { api_name: string; label: string; type: string; deleted_at: string }[];
  field_types: string[];
};

export type SetupApp = {
  id: string;
  key: string;
  label: string;
  description: string | null;
  icon: string;
  color: string;
  sort_order: number;
  is_active: boolean;
  tabs: { kind: string; object?: string }[];
  profile_ids: string[];
  pack_key: string | null;
};

export type PackInfo = {
  key: string;
  name: string;
  version: string;
  description: string;
  region: string;
  installed_version: string | null;
  is_enabled: boolean;
  upgrade_available: boolean;
  installed_at: string | null;
  custom_permissions: { name: string; label: string; profile_ids: string[] }[];
  contents: Record<string, number>;
};

export type PortalUser = {
  id: string;
  name: string;
  email: string;
  is_active: boolean;
  contact_id: string | null;
  last_login_at: string | null;
  has_password: boolean;
  created_at: string;
};

const json = <T>(path: string, method: "POST" | "PUT" | "PATCH" | "DELETE", body?: unknown) =>
  apiRequest<T>(path, { method, body });

export const setupApi = {
  catalog: (signal?: AbortSignal) => apiRequest<Catalog>("/setup/catalog", { signal }),
  profiles: (signal?: AbortSignal) => apiRequest<ProfileSummary[]>("/setup/profiles", { signal }),
  profile: (id: string, signal?: AbortSignal) =>
    apiRequest<ProfileDetail>(`/setup/profiles/${id}`, { signal }),
  createProfile: (body: { name: string; description?: string | null; clone_from_id?: string | null }) =>
    json<ProfileDetail>("/setup/profiles", "POST", body),
  updateProfile: (id: string, body: { name?: string; description?: string | null }) =>
    json<ProfileDetail>(`/setup/profiles/${id}`, "PATCH", body),
  deleteProfile: (id: string) => json<void>(`/setup/profiles/${id}`, "DELETE"),
  setSystemPermissions: (id: string, permissions: string[]) =>
    json<ProfileDetail>(`/setup/profiles/${id}/system-permissions`, "PUT", { permissions }),
  setObjectPermissions: (id: string, objects: Record<string, Partial<ObjectAccess>>) =>
    json<ProfileDetail>(`/setup/profiles/${id}/object-permissions`, "PUT", { objects }),
  setFieldPermissions: (
    id: string,
    fields: { object_api_name: string; field_api_name: string; access: "hidden" | "read" | "edit" | null }[],
  ) => json<ProfileDetail>(`/setup/profiles/${id}/field-permissions`, "PUT", { fields }),
  roles: (signal?: AbortSignal) => apiRequest<RoleInfo[]>("/setup/roles", { signal }),
  createRole: (body: { name: string; parent_id: string | null; description?: string | null }) =>
    json<RoleInfo>("/setup/roles", "POST", body),
  updateRole: (id: string, body: { name?: string; parent_id?: string | null; description?: string | null }) =>
    json<RoleInfo>(`/setup/roles/${id}`, "PATCH", body),
  deleteRole: (id: string) => json<void>(`/setup/roles/${id}`, "DELETE"),
  sharingDefaults: (signal?: AbortSignal) =>
    apiRequest<SharingDefault[]>("/setup/sharing-defaults", { signal }),
  setSharingDefault: (api: string, body: { access: string; grant_access_using_hierarchy: boolean }) =>
    json<SharingDefault>(`/setup/sharing-defaults/${api}`, "PUT", body),
  groups: (signal?: AbortSignal) => apiRequest<Group[]>("/setup/groups", { signal }),
  saveGroup: (id: string | null, body: { name: string; description?: string | null }) =>
    id ? json<Group>(`/setup/groups/${id}`, "PUT", body) : json<Group>("/setup/groups", "POST", body),
  setGroupMembers: (
    id: string,
    body: { user_ids: string[]; roles: { role_id: string; include_subordinates: boolean }[] },
  ) => json<Group>(`/setup/groups/${id}/members`, "PUT", body),
  deleteGroup: (id: string) => json<void>(`/setup/groups/${id}`, "DELETE"),
  queues: (signal?: AbortSignal) => apiRequest<Queue[]>("/setup/queues", { signal }),
  saveQueue: (
    id: string | null,
    body: { name: string; email?: string | null; object_api_names: string[] },
  ) => (id ? json<Queue>(`/setup/queues/${id}`, "PUT", body) : json<Queue>("/setup/queues", "POST", body)),
  setQueueMembers: (id: string, user_ids: string[]) =>
    json<Queue>(`/setup/queues/${id}/members`, "PUT", { user_ids }),
  deleteQueue: (id: string) => json<void>(`/setup/queues/${id}`, "DELETE"),
  sharingRules: (object?: string, signal?: AbortSignal) =>
    apiRequest<SharingRule[]>(`/setup/sharing-rules${toQueryString({ object_api_name: object })}`, {
      signal,
    }),
  saveSharingRule: (id: string | null, body: Omit<SharingRule, "id">) =>
    id
      ? json<SharingRule>(`/setup/sharing-rules/${id}`, "PUT", body)
      : json<SharingRule>("/setup/sharing-rules", "POST", body),
  deleteSharingRule: (id: string) => json<void>(`/setup/sharing-rules/${id}`, "DELETE"),
  objects: (signal?: AbortSignal) => apiRequest<SetupObjectSummary[]>("/setup/objects", { signal }),
  object: (api: string, signal?: AbortSignal) => apiRequest<SetupObject>(`/setup/objects/${api}`, { signal }),
  createObject: (body: Record<string, unknown>) => json<SetupObject>("/setup/objects", "POST", body),
  updateObject: (api: string, body: Record<string, unknown>) =>
    json<SetupObject>(`/setup/objects/${api}`, "PATCH", body),
  deleteObject: (api: string) => json<void>(`/setup/objects/${api}`, "DELETE"),
  createField: (api: string, body: Record<string, unknown>) =>
    json<SetupObject>(`/setup/objects/${api}/fields`, "POST", body),
  updateField: (api: string, field: string, body: Record<string, unknown>) =>
    json<SetupObject>(`/setup/objects/${api}/fields/${field}`, "PATCH", body),
  deleteField: (api: string, field: string) =>
    json<SetupObject>(`/setup/objects/${api}/fields/${field}`, "DELETE"),
  restoreField: (api: string, field: string) =>
    json<SetupObject>(`/setup/objects/${api}/fields/${field}/restore`, "POST"),
  apps: (signal?: AbortSignal) => apiRequest<SetupApp[]>("/setup/apps", { signal }),
  saveApp: (id: string | null, body: Record<string, unknown>) =>
    id ? json<SetupApp>(`/setup/apps/${id}`, "PUT", body) : json<SetupApp>("/setup/apps", "POST", body),
  deleteApp: (id: string) => json<void>(`/setup/apps/${id}`, "DELETE"),
  packs: (signal?: AbortSignal) => apiRequest<PackInfo[]>("/setup/packs", { signal }),
  installPack: (key: string) => json<PackInfo[]>(`/setup/packs/${key}/install`, "POST"),
  enablePack: (key: string, enabled: boolean) =>
    json<PackInfo[]>(`/setup/packs/${key}/${enabled ? "enable" : "disable"}`, "POST"),
  setPackPermission: (key: string, name: string, profile_ids: string[]) =>
    json<PackInfo[]>(`/setup/packs/${key}/permissions/${name}`, "PUT", { profile_ids }),
  settings: (signal?: AbortSignal) =>
    apiRequest<Record<string, Record<string, unknown>>>("/setup/settings", { signal }),
  saveSetting: (key: string, value: Record<string, unknown>) =>
    json<Record<string, unknown>>(`/setup/settings/${key}`, "PUT", { value }),
  portalUsers: (signal?: AbortSignal) => apiRequest<PortalUser[]>("/portal-users", { signal }),
  invitePortalUser: (contactId: string) => json<PortalUser>(`/portal-users/invite/${contactId}`, "POST"),
  setPortalUserActive: (id: string, active: boolean) =>
    json<PortalUser>(`/portal-users/${id}/${active ? "activate" : "deactivate"}`, "POST"),
  deletePortalUser: (id: string) => json<{ message: string }>(`/portal-users/${id}`, "DELETE"),
};

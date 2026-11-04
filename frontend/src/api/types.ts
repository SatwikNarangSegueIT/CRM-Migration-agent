export type Page<T> = { items: T[]; total: number; page: number; page_size: number };

export type MessageResponse = { message: string };

export type Ref = { id: string; name: string };

export type ObjectAccess = {
  read: boolean;
  create: boolean;
  edit: boolean;
  delete: boolean;
  view_all: boolean;
  modify_all: boolean;
};

export type FieldType =
  | "text"
  | "textarea"
  | "long_text"
  | "email"
  | "phone"
  | "url"
  | "number"
  | "percent"
  | "currency"
  | "date"
  | "datetime"
  | "time"
  | "checkbox"
  | "picklist"
  | "multi_picklist"
  | "lookup"
  | "master_detail"
  | "auto_number"
  | "address"
  | "encrypted_text"
  | "user"
  | "id"
  | "owner";

export type PicklistValue = {
  value: string;
  label: string;
  active: boolean;
  color?: string;
  default?: boolean;
  closed?: boolean;
  won?: boolean;
  probability?: number;
  forecast?: string;
};

export type FieldDescribe = {
  api_name: string;
  label: string;
  type: FieldType;
  help_text: string | null;
  required: boolean;
  is_unique: boolean;
  external_id: boolean;
  filterable: boolean;
  sortable: boolean;
  searchable: boolean;
  track_history: boolean;
  is_custom: boolean;
  is_standard: boolean;
  is_system: boolean;
  is_readonly: boolean;
  indexed: boolean;
  default_value: unknown;
  default_access: "hidden" | "read" | "edit";
  access: "hidden" | "read" | "edit";
  options: {
    values?: PicklistValue[];
    target?: string;
    targets?: string[];
    max_length?: number;
    scale?: number;
    min?: number;
    max?: number;
    is_path?: boolean;
    delete_rule?: string;
  };
};

export type ObjectSummary = {
  api_name: string;
  label: string;
  plural_label: string;
  description: string | null;
  icon: string;
  color: string;
  is_custom: boolean;
  pack_key: string | null;
  is_detail_only: boolean;
  searchable: boolean;
  allow_reports: boolean;
  access: ObjectAccess;
};

export type LayoutSection = { label: string; columns: 1 | 2; fields: string[] };
export type RelatedList = {
  object: string;
  field: string;
  label: string;
  columns: string[];
  object_label: string;
  can_create: boolean;
};

export type ListViewRef = {
  id: string;
  name: string;
  key: string | null;
  visibility: "private" | "public" | "shared";
  is_mine: boolean;
  kanban_field: string | null;
};

export type ObjectDescribe = ObjectSummary & {
  name_field_type: "text" | "auto_number";
  name_label: string;
  name_format: string | null;
  track_history: boolean;
  allow_activities: boolean;
  allow_files: boolean;
  allow_notes: boolean;
  allow_queues: boolean;
  show_in_portal: boolean;
  fields: Record<string, FieldDescribe>;
  page_layout: LayoutSection[];
  compact_layout: string[];
  list_columns: string[];
  related_lists: RelatedList[];
  activity_objects: { object: string; can_create: boolean }[];
  path_field: string | null;
  actions: { name: string; label: string; requires_edit: boolean }[];
  list_views: ListViewRef[];
};

export type AppTab =
  | { kind: "home"; label: string }
  | { kind: "object"; object: string; label: string; icon: string; color: string }
  | { kind: "calendar" | "reports" | "dashboards" | "queues"; label: string };

export type AppInfo = {
  id: string;
  key: string;
  label: string;
  description: string | null;
  icon: string;
  color: string;
  tabs: AppTab[];
  /** The workspace's domain app (law firm, accounting practice...), shown as the home page. */
  is_primary?: boolean;
};

export type LinkInfo = { id: string; name: string; object: string; object_label: string };

export type RecordData = {
  id: string;
  object: string;
  name: string;
  record_number: string | null;
  owner: { id: string; name: string; type: "user" | "queue" } | null;
  created_at: string;
  created_by: Ref | null;
  updated_at: string;
  updated_by: Ref | null;
  version: number;
  is_deleted: boolean;
  fields: Record<string, unknown>;
  display: Record<string, LinkInfo>;
  access: { edit: boolean; delete: boolean };
  actions?: { name: string; label: string }[];
};

export type RecordPage = {
  items: RecordData[];
  next_cursor: string | null;
  total: number;
  total_capped: boolean;
};

export type FilterCondition = { field: string; op: string; value?: unknown };
export type FilterNode = { logic: "and" | "or"; conditions: (FilterCondition | FilterNode)[] };
export type SortSpec = { field: string; direction: "asc" | "desc" };

export type ListViewDetail = {
  id: string;
  object_api_name: string;
  name: string;
  key: string | null;
  visibility: "private" | "public" | "shared";
  shared_profile_ids: string[];
  shared_role_ids: string[];
  scope: "mine" | "all" | "team" | "queue";
  columns: string[];
  filters: FilterNode | Record<string, never>;
  sort: SortSpec[];
  kanban_field: string | null;
  is_mine: boolean;
  can_edit: boolean;
};

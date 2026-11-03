import { apiRequest, toQueryString } from "./client";
import type { FilterNode, SortSpec } from "./types";

export type ChartType = "bar" | "column" | "line" | "donut" | "funnel" | "kpi" | "table";

export type ReportDefinition = {
  format: "tabular" | "summary" | "matrix";
  columns?: string[];
  filters?: FilterNode | null;
  scope?: "all" | "mine" | "team";
  group_by?: string[];
  group_columns?: string[];
  date_granularity?: Record<string, "day" | "week" | "month" | "quarter" | "year">;
  aggregates?: { op: "count" | "sum" | "avg" | "min" | "max"; field?: string }[];
  sort?: SortSpec[];
  chart?: { type: ChartType } | null;
  limit?: number;
};

export type Report = {
  id: string;
  name: string;
  key: string | null;
  description: string | null;
  folder_id: string | null;
  folder_name: string;
  object_api_name: string;
  object_label: string;
  definition: ReportDefinition;
  owner_id: string | null;
  updated_at: string;
  last_run_at: string | null;
  can_edit: boolean;
};

export type Folder = {
  id: string;
  name: string;
  key: string | null;
  visibility: "private" | "public" | "shared";
  is_mine: boolean;
  can_edit: boolean;
};

export type Cell = { value: unknown; label: string };

export type TabularResult = {
  format: "tabular";
  columns: { key: string; label: string; type: string }[];
  rows: { id: string; cells: Cell[] }[];
  truncated: boolean;
  totals: Record<string, number | null>;
};

export type GroupedResult = {
  format: "summary" | "matrix";
  dimensions: { key: string; label: string; type: string }[];
  row_dimensions: number;
  aggregates: { key: string; op: string; field: string | null; label: string }[];
  groups: { keys: unknown[]; labels: string[]; values: Record<string, number | null> }[];
  truncated: boolean;
  totals: Record<string, number | null>;
  chart: { type: ChartType } | null;
};

export type ReportResult = (TabularResult | GroupedResult) & {
  report: { id: string | null; name: string; object: string };
  run_at: string;
};

export type DashboardComponent = { report_id: string; title: string; chart: ChartType; width: 1 | 2 | 3 };

export type Dashboard = {
  id: string;
  name: string;
  key: string | null;
  description: string | null;
  folder_id: string | null;
  folder_name: string;
  running_user_id: string | null;
  components: DashboardComponent[];
  updated_at: string;
  can_edit: boolean;
};

export type ReportColumn = { key: string; label: string; type: string; group: string };

export type ReportInput = {
  name: string;
  description?: string | null;
  folder_id: string | null;
  object_api_name: string;
  definition: ReportDefinition;
};

export const analyticsApi = {
  folders: (signal?: AbortSignal) => apiRequest<Folder[]>("/report-folders", { signal }),
  createFolder: (body: { name: string; visibility: Folder["visibility"] }) =>
    apiRequest<Folder>("/report-folders", { method: "POST", body }),
  reports: (q?: string, signal?: AbortSignal) => apiRequest<Report[]>(`/reports${toQueryString({ q })}`, { signal }),
  report: (id: string, signal?: AbortSignal) => apiRequest<Report>(`/reports/${id}`, { signal }),
  columns: (object: string, signal?: AbortSignal) =>
    apiRequest<ReportColumn[]>(`/reports/columns/${object}`, { signal }),
  create: (body: ReportInput) => apiRequest<Report>("/reports", { method: "POST", body }),
  update: (id: string, body: ReportInput) => apiRequest<Report>(`/reports/${id}`, { method: "PUT", body }),
  remove: (id: string) => apiRequest<void>(`/reports/${id}`, { method: "DELETE" }),
  run: (id: string, body?: { filters?: FilterNode; scope?: string }, signal?: AbortSignal) =>
    apiRequest<ReportResult>(`/reports/${id}/run`, { method: "POST", body: body ?? {}, signal }),
  preview: (body: ReportInput, signal?: AbortSignal) =>
    apiRequest<ReportResult>("/reports/run", { method: "POST", body, signal }),
  schedules: (id: string, signal?: AbortSignal) =>
    apiRequest<{ id: string; frequency: string; recipients: string[]; next_run_at: string; is_mine: boolean }[]>(
      `/reports/${id}/schedules`,
      { signal },
    ),
  schedule: (id: string, body: { frequency: string; recipients: string[] }) =>
    apiRequest<unknown>(`/reports/${id}/schedules`, { method: "POST", body }),
  unschedule: (id: string, scheduleId: string) =>
    apiRequest<void>(`/reports/${id}/schedules/${scheduleId}`, { method: "DELETE" }),
  dashboards: (signal?: AbortSignal) => apiRequest<Dashboard[]>("/dashboards", { signal }),
  dashboard: (id: string, signal?: AbortSignal) => apiRequest<Dashboard>(`/dashboards/${id}`, { signal }),
  saveDashboard: (
    id: string | null,
    body: { name: string; description?: string | null; folder_id: string | null; components: DashboardComponent[] },
  ) =>
    id
      ? apiRequest<Dashboard>(`/dashboards/${id}`, { method: "PUT", body })
      : apiRequest<Dashboard>("/dashboards", { method: "POST", body }),
  removeDashboard: (id: string) => apiRequest<void>(`/dashboards/${id}`, { method: "DELETE" }),
  runDashboard: (id: string, signal?: AbortSignal) =>
    apiRequest<{
      dashboard: Dashboard;
      viewing_as: string | null;
      run_at: string;
      components: (DashboardComponent & { result: ReportResult | null; error: string | null })[];
    }>(`/dashboards/${id}/run`, { method: "POST", body: {}, signal }),
};

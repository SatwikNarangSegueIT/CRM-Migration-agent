import { apiRequest } from "./client";
import type { FilterNode } from "./types";

export type ImportAnalysis = {
  headers: string[];
  row_count: number;
  sample: Record<string, string>[];
  suggested_mapping: Record<string, string>;
  fields: { api_name: string; label: string; type: string; required: boolean }[];
  match_fields: string[];
};

export type ImportInput = {
  object_api_name: string;
  file_name: string;
  csv: string;
  mapping: Record<string, string>;
  match_field: string | null;
  duplicate_action: "skip" | "update" | "create";
  dry_run?: boolean;
};

export type ImportJob = {
  id: string;
  object_api_name: string;
  status: "pending" | "running" | "completed" | "failed";
  file_name: string;
  total_rows: number;
  created: number;
  updated: number;
  skipped: number;
  errors: number;
  created_at: string;
  finished_at: string | null;
  error_rows?: { row: number; message: string }[];
};

export type DryRun = {
  dry_run: true;
  total_rows: number;
  created: number;
  updated: number;
  skipped: number;
  errors: number;
  error_rows: { row: number; message: string }[];
  preview: { row: number; outcome: string; message?: string; values: Record<string, string> }[];
};

export type ExportInput = {
  object_api_name: string;
  view_id?: string | null;
  columns?: string[];
  filters?: FilterNode | null;
  scope?: "all" | "mine" | "team" | "queue";
};

export const dataApi = {
  analyze: (object_api_name: string, csv: string) =>
    apiRequest<ImportAnalysis>("/imports/analyze", { method: "POST", body: { object_api_name, csv } }),
  dryRun: (body: ImportInput) => apiRequest<DryRun>("/imports", { method: "POST", body: { ...body, dry_run: true } }),
  start: (body: ImportInput) => apiRequest<ImportJob>("/imports", { method: "POST", body }),
  jobs: (signal?: AbortSignal) => apiRequest<ImportJob[]>("/imports", { signal }),
  job: (id: string, signal?: AbortSignal) => apiRequest<ImportJob>(`/imports/${id}`, { signal }),
};

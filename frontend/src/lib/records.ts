// Metadata hooks and value formatting shared by list views, record pages, reports and the portal.
import { useQuery } from "@tanstack/react-query";
import { metaApi } from "../api/records";
import type { FieldDescribe, ObjectDescribe, PicklistValue, RecordData } from "../api/types";

export const TIME_ZONE = "Australia/Sydney";
const LOCALE = "en-AU";

export function useObjectMeta(api: string | undefined) {
  return useQuery({
    queryKey: ["meta", "object", api],
    queryFn: ({ signal }) => metaApi.object(api!, signal),
    enabled: Boolean(api),
    staleTime: 5 * 60_000,
  });
}

export function useObjects() {
  return useQuery({
    queryKey: ["meta", "objects"],
    queryFn: ({ signal }) => metaApi.objects(signal),
    staleTime: 5 * 60_000,
  });
}

export function useApps() {
  return useQuery({
    queryKey: ["meta", "apps"],
    queryFn: ({ signal }) => metaApi.apps(signal),
    staleTime: 5 * 60_000,
  });
}

export function recordPath(object: string, id: string): string {
  return `/o/${object}/${id}`;
}

const currency = new Intl.NumberFormat(LOCALE, { style: "currency", currency: "AUD" });
const numberFmt = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 6 });

export function formatCurrency(value: unknown): string {
  if (value === null || value === undefined || value === "") return "";
  const n = Number(value);
  return Number.isFinite(n) ? currency.format(n) : String(value);
}

export function formatNumber(value: unknown): string {
  if (value === null || value === undefined || value === "") return "";
  const n = Number(value);
  return Number.isFinite(n) ? numberFmt.format(n) : String(value);
}

export function formatDate(value: unknown): string {
  if (!value) return "";
  const s = String(value);
  const d = new Date(s.length === 10 ? `${s}T00:00:00` : s);
  if (Number.isNaN(d.getTime())) return s;
  return new Intl.DateTimeFormat(LOCALE, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    ...(s.length === 10 ? {} : { timeZone: TIME_ZONE }),
  }).format(d);
}

export function formatDateTimeValue(value: unknown): string {
  if (!value) return "";
  const d = new Date(String(value));
  if (Number.isNaN(d.getTime())) return String(value);
  return new Intl.DateTimeFormat(LOCALE, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: TIME_ZONE,
  }).format(d);
}

export function picklistValue(field: FieldDescribe | undefined, value: unknown): PicklistValue | undefined {
  return field?.options.values?.find((v) => v.value === value);
}

export type Address = { street?: string; city?: string; state?: string; postcode?: string; country?: string };

export function formatAddress(value: unknown): string {
  if (!value || typeof value !== "object") return "";
  const a = value as Address;
  const line2 = [a.city, a.state, a.postcode].filter(Boolean).join(" ");
  return [a.street, line2, a.country].filter(Boolean).join(", ");
}

/** Plain-text rendering of any field value (lists, exports, titles). */
export function formatValue(field: FieldDescribe | undefined, record: RecordData, apiName: string): string {
  if (apiName === "name") return record.name;
  if (apiName === "owner_id") return record.owner?.name ?? "";
  if (apiName === "created_at" || apiName === "updated_at") return formatDateTimeValue(record[apiName]);
  if (apiName === "created_by_id") return record.created_by?.name ?? "";
  if (apiName === "updated_by_id") return record.updated_by?.name ?? "";
  const value = record.fields[apiName];
  if (value === null || value === undefined) return "";
  switch (field?.type) {
    case "lookup":
    case "master_detail":
    case "user":
      return record.display[apiName]?.name ?? "";
    case "currency":
      return formatCurrency(value);
    case "percent":
      return `${formatNumber(value)}%`;
    case "number":
      return formatNumber(value);
    case "date":
      return formatDate(value);
    case "datetime":
      return formatDateTimeValue(value);
    case "checkbox":
      return value ? "Yes" : "No";
    case "picklist":
      return picklistValue(field, value)?.label ?? String(value);
    case "multi_picklist":
      return Array.isArray(value) ? value.map((v) => picklistValue(field, v)?.label ?? v).join("; ") : "";
    case "address":
      return formatAddress(value);
    default:
      return String(value);
  }
}

export function fieldLabel(meta: ObjectDescribe | undefined, apiName: string): string {
  return meta?.fields[apiName]?.label ?? apiName;
}

/** Fields the user may edit in a create/edit form (layout order first, then required fields not on the layout). */
export function editableFields(meta: ObjectDescribe, creating: boolean): string[] {
  const out: string[] = [];
  const add = (name: string) => {
    const f = meta.fields[name];
    if (!f || out.includes(name)) return;
    if (f.is_system && name !== "name") return;
    if (name === "name" && meta.name_field_type === "auto_number") return;
    if (f.access !== "edit" || f.is_readonly) return;
    if (name === "name" && (meta.fields.first_name || meta.fields.last_name)) return; // computed person names
    out.push(name);
  };
  for (const section of meta.page_layout) for (const name of section.fields) add(name);
  if (creating) for (const f of Object.values(meta.fields)) if (f.required) add(f.api_name);
  return out;
}

export function today(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

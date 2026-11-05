import { Link } from "react-router-dom";
import type { FieldDescribe, RecordData } from "../../api/types";
import {
  formatAddress,
  formatCurrency,
  formatDate,
  formatDateTimeValue,
  formatNumber,
  picklistValue,
  recordPath,
} from "../../lib/records";
import { CheckIcon } from "../icons";

export function PicklistPill({ field, value }: { field?: FieldDescribe; value: unknown }) {
  const pv = picklistValue(field, value);
  const color = pv?.color;
  return (
    <span className="inline-flex items-center gap-1.5">
      {color && (
        <span
          aria-hidden="true"
          className="h-2 w-2 flex-none rounded-full"
          style={{ backgroundColor: color }}
        />
      )}
      {pv?.label ?? String(value)}
    </span>
  );
}

/** Read-only rendering of one field of a record (links for lookups, formatted numbers and dates). */
export function FieldDisplay({
  field,
  record,
  apiName,
  linkBase = "",
}: {
  field?: FieldDescribe;
  record: RecordData;
  apiName: string;
  /** Prefix for record links ("/portal" inside the portal). */
  linkBase?: string;
}) {
  if (apiName === "name") return <span>{record.name}</span>;
  if (apiName === "owner_id") return <span>{record.owner?.name ?? ""}</span>;
  if (apiName === "created_by_id")
    return (
      <span>
        {record.created_by?.name}{" "}
        <span className="text-slate-500">{formatDateTimeValue(record.created_at)}</span>
      </span>
    );
  if (apiName === "updated_by_id")
    return (
      <span>
        {record.updated_by?.name}{" "}
        <span className="text-slate-500">{formatDateTimeValue(record.updated_at)}</span>
      </span>
    );
  if (apiName === "created_at" || apiName === "updated_at")
    return <span>{formatDateTimeValue(record[apiName])}</span>;

  const value = record.fields[apiName];
  if (value === null || value === undefined || value === "")
    return (
      <span className="text-slate-300" aria-label="empty">
        —
      </span>
    );

  switch (field?.type) {
    case "lookup":
    case "master_detail": {
      const link = record.display[apiName];
      if (!link) return null;
      return (
        <Link
          to={`${linkBase}${recordPath(link.object, link.id)}`}
          className="text-brand-700 hover:underline"
        >
          {link.name}
        </Link>
      );
    }
    case "user":
      return <span>{record.display[apiName]?.name}</span>;
    case "currency":
      return <span className="tabular-nums">{formatCurrency(value)}</span>;
    case "percent":
      return <span className="tabular-nums">{formatNumber(value)}%</span>;
    case "number":
      return <span className="tabular-nums">{formatNumber(value)}</span>;
    case "date":
      return <span>{formatDate(value)}</span>;
    case "datetime":
      return <span>{formatDateTimeValue(value)}</span>;
    case "checkbox":
      return value ? (
        <CheckIcon size={18} className="text-emerald-600" aria-label="Yes" />
      ) : (
        <span className="text-slate-400">No</span>
      );
    case "picklist":
      return <PicklistPill field={field} value={value} />;
    case "multi_picklist":
      return (
        <span className="flex flex-wrap gap-1">
          {(Array.isArray(value) ? value : []).map((v) => (
            <span key={String(v)} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-700">
              {picklistValue(field, v)?.label ?? String(v)}
            </span>
          ))}
        </span>
      );
    case "email":
      return (
        <a href={`mailto:${String(value)}`} className="break-all text-brand-700 hover:underline">
          {String(value)}
        </a>
      );
    case "phone":
      return (
        <a href={`tel:${String(value)}`} className="text-brand-700 hover:underline">
          {String(value)}
        </a>
      );
    case "url":
      return (
        <a
          href={String(value)}
          target="_blank"
          rel="noopener noreferrer"
          className="break-all text-brand-700 hover:underline"
        >
          {String(value).replace(/^https?:\/\//, "")}
        </a>
      );
    case "address":
      return <span className="whitespace-pre-line">{formatAddress(value).replace(", ", "\n")}</span>;
    case "long_text":
    case "textarea":
      return <span className="whitespace-pre-wrap break-words">{String(value)}</span>;
    case "encrypted_text":
      return <span className="font-mono">{String(value)}</span>;
    default:
      return <span className="break-words">{String(value)}</span>;
  }
}

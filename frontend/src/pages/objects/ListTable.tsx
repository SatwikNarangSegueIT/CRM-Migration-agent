import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "../../api/client";
import { recordsApi } from "../../api/records";
import type { ObjectDescribe, RecordData, SortSpec } from "../../api/types";
import { FieldDisplay } from "../../components/record/FieldDisplay";
import { FieldInput } from "../../components/record/FieldInput";
import { CheckIcon, ChevronDownIcon, CloseIcon, EditIcon } from "../../components/icons";
import { Spinner, useToast } from "../../components/ui";
import { cx } from "../../components/ui/cx";
import { recordPath } from "../../lib/records";

const INLINE_TYPES = new Set(["text", "email", "phone", "url", "number", "currency", "percent", "date", "picklist", "checkbox", "textarea"]);

function InlineCell({ meta, record, api, onSaved }: { meta: ObjectDescribe; record: RecordData; api: string; onSaved: (r: RecordData) => void }) {
  const toast = useToast();
  const f = meta.fields[api]!;
  const [value, setValue] = useState<unknown>(record.fields[api] ?? null);
  const save = useMutation({
    mutationFn: () => recordsApi.update(meta.api_name, record.id, { version: record.version, fields: { [api]: value === "" ? null : value } }),
    onSuccess: (r) => {
      onSaved(r);
      toast.show(`${meta.label} "${r.name}" was saved.`);
    },
    onError: (e) => toast.show(errorMessage(e), "error"),
  });
  return (
    <form
      className="flex items-center gap-1"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
      onKeyDown={(e) => {
        if (e.key === "Escape") onSaved(record);
      }}
    >
      <div className="min-w-[8rem] flex-1">
        <FieldInput id={`inline-${record.id}-${api}`} field={f} value={value} onChange={setValue} />
      </div>
      <button type="submit" aria-label="Save" className="rounded p-1 text-emerald-700 hover:bg-emerald-50" disabled={save.isPending}>
        <CheckIcon size={16} />
      </button>
      <button type="button" aria-label="Cancel" className="rounded p-1 text-slate-500 hover:bg-slate-100" onClick={() => onSaved(record)}>
        <CloseIcon size={16} />
      </button>
    </form>
  );
}

export function ListTable({
  meta,
  columns,
  rows,
  loading,
  sort,
  onSort,
  selected,
  onSelect,
  empty,
  footer,
  inlineEdit = true,
}: {
  meta: ObjectDescribe;
  columns: string[];
  rows: RecordData[];
  loading: boolean;
  sort: SortSpec | null;
  onSort: (field: string) => void;
  selected: Set<string>;
  onSelect: (ids: Set<string>) => void;
  empty: ReactNode;
  footer?: ReactNode;
  inlineEdit?: boolean;
}) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<{ id: string; api: string } | null>(null);
  const allSelected = rows.length > 0 && rows.every((r) => selected.has(r.id));

  function toggle(id: string) {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onSelect(next);
  }

  return (
    <div className="overflow-x-auto rounded-b-lg border border-slate-300 bg-white">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <caption className="sr-only">{meta.plural_label}</caption>
        <thead>
          <tr className="bg-white">
            <th scope="col" className="w-10 border-b border-slate-300 px-3 py-2">
              <input
                type="checkbox"
                aria-label="Select all"
                className="h-4 w-4 rounded border-slate-300"
                checked={allSelected}
                onChange={() => onSelect(allSelected ? new Set() : new Set(rows.map((r) => r.id)))}
              />
            </th>
            {columns.map((api) => {
              const f = meta.fields[api];
              const sortable = f?.sortable !== false;
              const active = sort?.field === api;
              return (
                <th key={api} scope="col" aria-sort={active ? (sort!.direction === "asc" ? "ascending" : "descending") : undefined} className="border-b border-slate-300 px-3 py-2 text-left text-xs font-semibold text-slate-700">
                  {sortable ? (
                    <button type="button" className="inline-flex items-center gap-1 hover:text-brand-700" onClick={() => onSort(api)}>
                      {f?.label ?? api}
                      <ChevronDownIcon size={14} className={cx("text-slate-400 transition-transform", active && "text-brand-700", active && sort!.direction === "asc" && "rotate-180")} />
                    </button>
                  ) : (
                    f?.label ?? api
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200">
          {loading && rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length + 1} className="px-4 py-8 text-center">
                <Spinner label="Loading records" />
              </td>
            </tr>
          ) : rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length + 1}>{empty}</td>
            </tr>
          ) : (
            rows.map((r) => (
              <tr key={r.id} className={cx("group hover:bg-slate-50", selected.has(r.id) && "bg-brand-50/60")}>
                <td className="px-3 py-2">
                  <input type="checkbox" aria-label={`Select ${r.name}`} className="h-4 w-4 rounded border-slate-300" checked={selected.has(r.id)} onChange={() => toggle(r.id)} />
                </td>
                {columns.map((api, i) => {
                  const f = meta.fields[api];
                  const isEditing = editing?.id === r.id && editing.api === api;
                  const canInline = inlineEdit && r.access.edit && f && f.access === "edit" && !f.is_readonly && !f.is_system && INLINE_TYPES.has(f.type);
                  return (
                    <td key={api} className="max-w-xs px-3 py-2 align-top text-slate-800">
                      {isEditing ? (
                        <InlineCell
                          meta={meta}
                          record={r}
                          api={api}
                          onSaved={() => {
                            setEditing(null);
                            void queryClient.invalidateQueries({ queryKey: ["records", meta.api_name] });
                          }}
                        />
                      ) : i === 0 || api === "name" ? (
                        <Link to={recordPath(meta.api_name, r.id)} className="font-medium text-brand-700 hover:underline">
                          {api === "name" ? r.name : <FieldDisplay field={f} record={r} apiName={api} />}
                        </Link>
                      ) : (
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0 truncate">
                            <FieldDisplay field={f} record={r} apiName={api} />
                          </div>
                          {canInline && (
                            <button type="button" aria-label={`Edit ${f!.label}`} className="invisible rounded p-0.5 text-slate-400 hover:text-brand-700 group-hover:visible focus:visible" onClick={() => setEditing({ id: r.id, api })}>
                              <EditIcon size={14} />
                            </button>
                          )}
                        </div>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))
          )}
        </tbody>
      </table>
      {footer}
    </div>
  );
}

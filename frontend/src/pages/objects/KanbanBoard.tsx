import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "../../api/client";
import { recordsApi } from "../../api/records";
import type { ObjectDescribe, RecordData } from "../../api/types";
import { FieldDisplay } from "../../components/record/FieldDisplay";
import { Alert, Spinner, useToast } from "../../components/ui";
import { cx } from "../../components/ui/cx";
import { formatCurrency, recordPath } from "../../lib/records";

/** Kanban for any object with a path picklist; drag a card to another column to change the value. */
export function KanbanBoard({
  meta,
  field,
  viewId,
  q,
}: {
  meta: ObjectDescribe;
  field: string;
  viewId: string | null;
  q: string;
}) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [dragging, setDragging] = useState<RecordData | null>(null);
  const [over, setOver] = useState<string | null>(null);
  const board = useQuery({
    queryKey: ["records", meta.api_name, "kanban", field, viewId, q],
    queryFn: ({ signal }) => recordsApi.kanban(meta.api_name, field, viewId, q, signal),
  });
  const move = useMutation({
    mutationFn: ({ record, value }: { record: RecordData; value: string }) => {
      const pv = meta.fields[field]?.options.values?.find((v) => v.value === value);
      if (pv?.closed && pv.won === false && meta.fields.loss_reason) {
        throw new Error("Open the record to close it as lost (a loss reason is required).");
      }
      return recordsApi.update(meta.api_name, record.id, {
        version: record.version,
        fields: { [field]: value },
      });
    },
    onSuccess: (r) => {
      toast.show(`${r.name} moved.`);
      void queryClient.invalidateQueries({ queryKey: ["records", meta.api_name] });
    },
    onError: (e) => toast.show(e instanceof Error && !("status" in e) ? e.message : errorMessage(e), "error"),
  });
  const compact = meta.compact_layout.filter((c) => c !== field).slice(0, 3);

  if (board.isPending)
    return (
      <div className="rounded-b-lg border border-slate-300 bg-white p-8">
        <Spinner label="Loading board" />
      </div>
    );
  if (board.isError) return <Alert tone="error">{errorMessage(board.error)}</Alert>;

  return (
    <div className="overflow-x-auto rounded-b-lg border border-slate-300 bg-slate-50 p-3">
      <div className="flex min-w-max gap-3">
        {board.data.columns.map((col) => (
          <section
            key={col.value}
            aria-label={`${col.label} (${col.total})`}
            onDragOver={(e) => {
              e.preventDefault();
              setOver(col.value);
            }}
            onDragLeave={() => setOver((o) => (o === col.value ? null : o))}
            onDrop={(e) => {
              e.preventDefault();
              setOver(null);
              if (dragging && dragging.fields[field] !== col.value)
                move.mutate({ record: dragging, value: col.value });
              setDragging(null);
            }}
            className={cx(
              "flex w-72 flex-none flex-col rounded-lg border bg-white",
              over === col.value ? "border-brand-500 ring-2 ring-brand-200" : "border-slate-200",
            )}
          >
            <header
              className="border-b border-slate-200 px-3 py-2"
              style={{ borderTop: `3px solid ${col.color ?? "#94a3b8"}` }}
            >
              <p className="flex items-center justify-between text-sm font-semibold text-slate-900">
                {col.label}
                <span className="rounded-full bg-slate-100 px-2 text-xs text-slate-600">{col.total}</span>
              </p>
              {col.amount !== null && <p className="text-xs text-slate-500">{formatCurrency(col.amount)}</p>}
            </header>
            <ul className="flex min-h-[6rem] flex-col gap-2 p-2">
              {col.items.map((r) => (
                <li
                  key={r.id}
                  draggable={r.access.edit}
                  onDragStart={() => setDragging(r)}
                  onDragEnd={() => setDragging(null)}
                  className={cx(
                    "rounded-md border border-slate-200 bg-white p-2.5 text-sm shadow-sm",
                    r.access.edit && "cursor-grab hover:border-brand-300",
                  )}
                >
                  <Link
                    to={recordPath(meta.api_name, r.id)}
                    className="font-medium text-brand-700 hover:underline"
                  >
                    {r.name}
                  </Link>
                  <dl className="mt-1 space-y-0.5 text-xs text-slate-600">
                    {compact.map((api) => (
                      <div key={api} className="flex gap-1">
                        <dt className="sr-only">{meta.fields[api]?.label}</dt>
                        <dd className="truncate">
                          <FieldDisplay field={meta.fields[api]} record={r} apiName={api} />
                        </dd>
                      </div>
                    ))}
                  </dl>
                </li>
              ))}
              {col.total > col.items.length && (
                <li className="px-1 text-xs text-slate-500">
                  +{col.total - col.items.length} more — refine the list to see them
                </li>
              )}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}

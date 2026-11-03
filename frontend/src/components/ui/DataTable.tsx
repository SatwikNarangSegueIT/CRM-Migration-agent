import type { ReactNode } from "react";
import { ChevronDownIcon } from "../icons";
import { Spinner } from "./Spinner";
import { cx } from "./cx";

export type Column<T> = {
  key: string;
  header: ReactNode;
  render: (row: T) => ReactNode;
  className?: string;
  /** Hide the decorative header chevron (e.g. for action columns). */
  noMenu?: boolean;
};

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  loading = false,
  emptyMessage = "No records to display.",
  caption,
  renderExpanded,
  attached = false,
}: {
  columns: Column<T>[];
  rows: T[] | undefined;
  rowKey: (row: T) => string;
  loading?: boolean;
  emptyMessage?: ReactNode;
  caption?: string;
  /** Optional extra row rendered below a row (e.g. details). Return null to skip. */
  renderExpanded?: (row: T) => ReactNode;
  /** Visually attach to a ListViewHeader above (square top corners). */
  attached?: boolean;
}) {
  return (
    <div
      className={cx(
        "overflow-x-auto border border-slate-300 bg-white",
        attached ? "rounded-b-lg" : "rounded-lg shadow-sm",
      )}
    >
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead className="bg-white">
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                scope="col"
                className={cx(
                  "border-b border-slate-300 px-4 py-2 text-left text-xs font-semibold text-slate-700",
                  col.className,
                )}
              >
                <span className="inline-flex items-center gap-1">
                  {col.header}
                  {!col.noMenu && <ChevronDownIcon size={14} className="text-slate-400" />}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200">
          {loading ? (
            <tr>
              <td colSpan={columns.length} className="px-4 py-8 text-center">
                <Spinner label="Loading records" />
              </td>
            </tr>
          ) : !rows || rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="text-slate-500">
                {typeof emptyMessage === "string" ? (
                  <p className="px-4 py-8 text-center">{emptyMessage}</p>
                ) : (
                  emptyMessage
                )}
              </td>
            </tr>
          ) : (
            rows.map((row) => {
              const expanded = renderExpanded?.(row);
              return (
                <RowGroup key={rowKey(row)}>
                  <tr className="hover:bg-slate-50">
                    {columns.map((col) => (
                      <td key={col.key} className={cx("px-4 py-2.5 align-top text-slate-800", col.className)}>
                        {col.render(row)}
                      </td>
                    ))}
                  </tr>
                  {expanded ? (
                    <tr className="bg-slate-50">
                      <td colSpan={columns.length} className="px-4 py-3">
                        {expanded}
                      </td>
                    </tr>
                  ) : null}
                </RowGroup>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}

function RowGroup({ children }: { children: ReactNode }) {
  return <>{children}</>;
}

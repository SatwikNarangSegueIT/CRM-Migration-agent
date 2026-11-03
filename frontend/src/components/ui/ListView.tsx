import { useState, type FormEvent, type ReactNode } from "react";
import { SearchIcon } from "../icons";
import { cx } from "./cx";

/** Grouped outlined buttons, e.g. New | Refresh. */
export function ButtonGroup({ children, label }: { children: ReactNode; label: string }) {
  return (
    <div
      role="group"
      aria-label={label}
      className="inline-flex divide-x divide-slate-300 overflow-hidden rounded-md border border-slate-300 bg-white shadow-sm"
    >
      {children}
    </div>
  );
}

export const groupButtonClass =
  "inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-brand-700 hover:bg-slate-50 " +
  "focus-visible:relative focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-700 " +
  "disabled:cursor-not-allowed disabled:text-slate-400";

export function ListSearch({
  initial,
  onSearch,
  label = "Search this list",
}: {
  initial: string;
  onSearch: (value: string) => void;
  label?: string;
}) {
  const [value, setValue] = useState(initial);
  function onSubmit(event: FormEvent) {
    event.preventDefault();
    onSearch(value.trim());
  }
  return (
    <form role="search" onSubmit={onSubmit} className="w-full sm:w-64">
      <label className="sr-only" htmlFor="list-search">
        {label}
      </label>
      <div className="relative">
        <SearchIcon
          size={16}
          className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400"
        />
        <input
          id="list-search"
          type="search"
          placeholder="Search this list..."
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="h-8 w-full rounded-md border border-slate-300 bg-white pl-8 pr-3 text-sm placeholder:text-slate-500 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200"
        />
      </div>
    </form>
  );
}

/**
 * List view header: small object label over a large view title with an icon badge, a meta line
 * ("12 items • Sorted by Name • Updated a few seconds ago"), actions at top-right and a toolbar row.
 */
export function ListViewHeader({
  objectLabel,
  title,
  icon,
  iconClassName = "bg-brand-600",
  meta,
  actions,
  toolbar,
}: {
  objectLabel: string;
  title: string;
  icon: ReactNode;
  iconClassName?: string;
  meta?: ReactNode;
  actions?: ReactNode;
  toolbar?: ReactNode;
}) {
  return (
    <div className="rounded-t-lg border border-b-0 border-slate-300 bg-slate-50 px-4 pb-3 pt-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <span
            aria-hidden="true"
            className={cx(
              "flex h-9 w-9 flex-none items-center justify-center rounded-md text-white",
              iconClassName,
            )}
          >
            {icon}
          </span>
          <div className="min-w-0">
            <p className="text-xs text-slate-600">{objectLabel}</p>
            <h1 className="truncate text-lg font-bold text-slate-900">{title}</h1>
          </div>
        </div>
        {actions}
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-slate-600" aria-live="polite">
          {meta}
        </p>
        {toolbar && <div className="flex flex-wrap items-center gap-2">{toolbar}</div>}
      </div>
    </div>
  );
}

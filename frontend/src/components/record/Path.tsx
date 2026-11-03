import { useState } from "react";
import type { FieldDescribe } from "../../api/types";
import { CheckIcon } from "../icons";
import { Button } from "../ui";
import { cx } from "../ui/cx";

/** Stage path for a path picklist: completed / current / upcoming chevrons with "Mark as current". */
export function Path({
  field,
  value,
  canEdit,
  saving,
  onMark,
}: {
  field: FieldDescribe;
  value: unknown;
  canEdit: boolean;
  saving: boolean;
  onMark: (value: string) => void;
}) {
  const values = (field.options.values ?? []).filter((v) => v.active || v.value === value);
  const currentIndex = values.findIndex((v) => v.value === value);
  const [selected, setSelected] = useState<string | null>(null);
  const current = values[currentIndex];
  const closed = Boolean(current?.closed);
  // Show only one terminal "closed" step (the reached one), like other CRMs' paths.
  const visible = values.filter((v, i) => !v.closed || i === currentIndex || (!closed && v === values.find((x) => x.closed)));
  const chosen = selected && selected !== value ? selected : null;

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
      <ol className="flex flex-wrap gap-1 sm:flex-nowrap" aria-label={`${field.label} path`}>
        {visible.map((v) => {
          const i = values.indexOf(v);
          const done = currentIndex >= 0 && i < currentIndex && !closed;
          const isCurrent = i === currentIndex;
          const isSelected = v.value === chosen;
          const label = v.closed && !isCurrent ? "Closed" : v.label;
          return (
            <li key={v.value} className="min-w-0 flex-1">
              <button
                type="button"
                disabled={!canEdit || closed}
                onClick={() => setSelected(v.value === selected ? null : v.value)}
                aria-current={isCurrent ? "step" : undefined}
                className={cx(
                  "relative flex h-9 w-full items-center justify-center gap-1 truncate px-4 text-xs font-semibold transition-colors",
                  "first:rounded-l-full last:rounded-r-full [clip-path:polygon(0_0,calc(100%-10px)_0,100%_50%,calc(100%-10px)_100%,0_100%,10px_50%)]",
                  "first:[clip-path:polygon(0_0,calc(100%-10px)_0,100%_50%,calc(100%-10px)_100%,0_100%)]",
                  isSelected
                    ? "bg-brand-800 text-white"
                    : isCurrent
                      ? v.closed && v.won === false
                        ? "bg-red-600 text-white"
                        : "bg-brand-700 text-white"
                      : done
                        ? "bg-emerald-600 text-white hover:bg-emerald-700"
                        : "bg-slate-100 text-slate-700 hover:bg-slate-200",
                  "disabled:cursor-default",
                )}
                title={v.label}
              >
                {done && <CheckIcon size={14} />}
                <span className="truncate">{label}</span>
              </button>
            </li>
          );
        })}
      </ol>
      {canEdit && !closed && (
        <div className="mt-2 flex justify-end">
          <Button
            size="sm"
            loading={saving}
            disabled={!chosen && currentIndex >= values.length - 1}
            onClick={() => {
              const next = chosen ?? values[currentIndex + 1]?.value;
              if (next) onMark(next);
              setSelected(null);
            }}
          >
            {chosen ? "Mark as Current Stage" : `Mark ${field.label} as Complete`}
          </Button>
        </div>
      )}
    </div>
  );
}

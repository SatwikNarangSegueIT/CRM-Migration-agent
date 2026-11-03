import { useQuery } from "@tanstack/react-query";
import { useEffect, useId, useRef, useState } from "react";
import { metaApi, recordsApi } from "../../api/records";
import type { FieldDescribe } from "../../api/types";
import { useDismiss } from "../../lib/useDismiss";
import { CloseIcon, SearchIcon } from "../icons";
import { cx } from "../ui/cx";

const CONTROL =
  "block w-full rounded-md border bg-white px-3 py-2 text-sm text-slate-900 shadow-sm placeholder:text-slate-400 " +
  "focus:outline-none focus:ring-2 focus:ring-brand-500 disabled:bg-slate-100 disabled:text-slate-500";

export function controlClass(invalid?: boolean, extra?: string) {
  return cx(CONTROL, invalid ? "border-red-400" : "border-slate-300", extra);
}

type Props = {
  id: string;
  field: FieldDescribe;
  value: unknown;
  onChange: (value: unknown) => void;
  invalid?: boolean;
  describedBy?: string;
  /** Display name of the current lookup/user value. */
  displayName?: string;
  disabled?: boolean;
};

function useDebounced<T>(value: T, ms = 250): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = window.setTimeout(() => setV(value), ms);
    return () => window.clearTimeout(t);
  }, [value, ms]);
  return v;
}

type Option = { id: string; name: string; detail?: unknown };

/** Typeahead combobox used for lookups and user fields. */
export function Combobox({
  id,
  value,
  displayName,
  onChange,
  search,
  placeholder,
  invalid,
  describedBy,
  disabled,
  queryKey,
}: {
  id: string;
  value: string | null;
  displayName?: string;
  onChange: (id: string | null, name: string | null) => void;
  search: (q: string, signal: AbortSignal) => Promise<Option[]>;
  placeholder?: string;
  invalid?: boolean;
  describedBy?: string;
  disabled?: boolean;
  queryKey: unknown[];
}) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [active, setActive] = useState(0);
  const [label, setLabel] = useState(displayName ?? "");
  const ref = useRef<HTMLDivElement>(null);
  const listId = useId();
  useDismiss(open, ref, () => setOpen(false));
  useEffect(() => setLabel(displayName ?? ""), [displayName]);
  const q = useDebounced(text);
  const results = useQuery({
    queryKey: [...queryKey, q],
    queryFn: ({ signal }) => search(q, signal),
    enabled: open,
    staleTime: 15_000,
  });
  const options = results.data ?? [];

  function choose(option: Option) {
    onChange(option.id, option.name);
    setLabel(option.name);
    setText("");
    setOpen(false);
  }

  if (value && !open) {
    return (
      <div className={controlClass(invalid, "flex items-center justify-between gap-2 py-1.5")}>
        <span className="truncate">{label || "Selected"}</span>
        {!disabled && (
          <button
            type="button"
            className="rounded p-0.5 text-slate-500 hover:bg-slate-100"
            aria-label={`Clear ${label}`}
            onClick={() => {
              onChange(null, null);
              setLabel("");
              setOpen(true);
            }}
          >
            <CloseIcon size={14} />
          </button>
        )}
      </div>
    );
  }

  return (
    <div ref={ref} className="relative">
      <SearchIcon size={16} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
      <input
        id={id}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-invalid={invalid || undefined}
        aria-describedby={describedBy}
        disabled={disabled}
        autoComplete="off"
        className={controlClass(invalid, "pl-8")}
        placeholder={placeholder ?? "Search..."}
        value={text}
        onFocus={() => setOpen(true)}
        onChange={(e) => {
          setText(e.target.value);
          setActive(0);
          setOpen(true);
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setActive((a) => Math.min(a + 1, options.length - 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((a) => Math.max(a - 1, 0));
          } else if (e.key === "Enter" && open && options[active]) {
            e.preventDefault();
            choose(options[active]);
          }
        }}
      />
      {open && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-30 mt-1 max-h-64 w-full overflow-auto rounded-md border border-slate-200 bg-white py-1 text-sm shadow-lg"
        >
          {results.isFetching && options.length === 0 && <li className="px-3 py-2 text-slate-500">Searching…</li>}
          {!results.isFetching && options.length === 0 && <li className="px-3 py-2 text-slate-500">No matches</li>}
          {options.map((option, i) => (
            <li
              key={option.id}
              role="option"
              aria-selected={i === active}
              className={cx("cursor-pointer px-3 py-2", i === active ? "bg-brand-50" : "hover:bg-slate-50")}
              onMouseDown={(e) => {
                e.preventDefault();
                choose(option);
              }}
              onMouseEnter={() => setActive(i)}
            >
              <span className="block text-slate-900">{option.name}</span>
              {option.detail != null && option.detail !== "" && (
                <span className="block text-xs text-slate-500">{String(option.detail)}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function toLocalInput(value: unknown): string {
  if (!value) return "";
  const d = new Date(String(value));
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Editable control for one field, chosen by type. Values follow the API's stored representation. */
export function FieldInput({ id, field, value, onChange, invalid, describedBy, displayName, disabled }: Props) {
  const common = { id, "aria-invalid": invalid || undefined, "aria-describedby": describedBy, disabled };
  switch (field.type) {
    case "checkbox":
      return (
        <input
          {...common}
          type="checkbox"
          className="h-4 w-4 rounded border-slate-300 text-brand-700 focus:ring-brand-500"
          checked={Boolean(value)}
          onChange={(e) => onChange(e.target.checked)}
        />
      );
    case "picklist":
      return (
        <select {...common} className={controlClass(invalid)} value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value || null)}>
          <option value="">--None--</option>
          {(field.options.values ?? [])
            .filter((v) => v.active || v.value === value)
            .map((v) => (
              <option key={v.value} value={v.value}>
                {v.label}
              </option>
            ))}
        </select>
      );
    case "multi_picklist": {
      const selected = new Set(Array.isArray(value) ? (value as string[]) : []);
      return (
        <div id={id} role="group" aria-describedby={describedBy} className="flex flex-wrap gap-x-4 gap-y-1">
          {(field.options.values ?? [])
            .filter((v) => v.active)
            .map((v) => (
              <label key={v.value} className="inline-flex items-center gap-1.5 text-sm">
                <input
                  type="checkbox"
                  disabled={disabled}
                  className="h-4 w-4 rounded border-slate-300 text-brand-700"
                  checked={selected.has(v.value)}
                  onChange={(e) => {
                    const next = new Set(selected);
                    if (e.target.checked) next.add(v.value);
                    else next.delete(v.value);
                    onChange([...next]);
                  }}
                />
                {v.label}
              </label>
            ))}
        </div>
      );
    }
    case "lookup":
    case "master_detail": {
      const targets = field.options.targets ?? (field.options.target ? [field.options.target] : []);
      return (
        <PolymorphicLookup
          id={id}
          targets={targets}
          value={(value as string) ?? null}
          displayName={displayName}
          onChange={onChange}
          invalid={invalid}
          describedBy={describedBy}
          disabled={disabled}
        />
      );
    }
    case "user":
      return (
        <Combobox
          id={id}
          value={(value as string) ?? null}
          displayName={displayName}
          onChange={(v) => onChange(v)}
          search={(q, signal) => metaApi.users(q, signal).then((rows) => rows.map((u) => ({ id: u.id, name: u.name, detail: u.title ?? u.email })))}
          queryKey={["user-picker"]}
          placeholder="Search users..."
          invalid={invalid}
          describedBy={describedBy}
          disabled={disabled}
        />
      );
    case "date":
      return <input {...common} type="date" className={controlClass(invalid)} value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value || null)} />;
    case "datetime":
      return (
        <input
          {...common}
          type="datetime-local"
          className={controlClass(invalid)}
          value={toLocalInput(value)}
          onChange={(e) => onChange(e.target.value ? new Date(e.target.value).toISOString() : null)}
        />
      );
    case "time":
      return <input {...common} type="time" className={controlClass(invalid)} value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value || null)} />;
    case "number":
    case "currency":
    case "percent":
      return (
        <div className="relative">
          {field.type === "currency" && <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-slate-500">$</span>}
          <input
            {...common}
            type="number"
            inputMode="decimal"
            step={field.options.scale !== undefined ? String(10 ** -field.options.scale) : field.type === "number" ? "1" : "0.01"}
            className={controlClass(invalid, cx(field.type === "currency" && "pl-7", field.type === "percent" && "pr-8"))}
            value={value === null || value === undefined ? "" : String(value)}
            onChange={(e) => onChange(e.target.value === "" ? null : e.target.value)}
          />
          {field.type === "percent" && <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-sm text-slate-500">%</span>}
        </div>
      );
    case "textarea":
    case "long_text":
      return (
        <textarea
          {...common}
          rows={field.type === "long_text" ? 5 : 3}
          maxLength={field.options.max_length}
          className={controlClass(invalid)}
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
        />
      );
    case "address": {
      const a = (value && typeof value === "object" ? value : {}) as Record<string, string>;
      const set = (k: string, v: string) => onChange({ ...a, [k]: v });
      return (
        <div id={id} role="group" aria-describedby={describedBy} className="grid gap-2 sm:grid-cols-6">
          <input aria-label="Street" placeholder="Street" disabled={disabled} className={controlClass(invalid, "sm:col-span-6")} value={a.street ?? ""} onChange={(e) => set("street", e.target.value)} />
          <input aria-label="City / suburb" placeholder="City / suburb" disabled={disabled} className={controlClass(invalid, "sm:col-span-3")} value={a.city ?? ""} onChange={(e) => set("city", e.target.value)} />
          <input aria-label="State" placeholder="State" disabled={disabled} className={controlClass(invalid, "sm:col-span-1")} value={a.state ?? ""} onChange={(e) => set("state", e.target.value)} />
          <input aria-label="Postcode" placeholder="Postcode" disabled={disabled} className={controlClass(invalid, "sm:col-span-2")} value={a.postcode ?? ""} onChange={(e) => set("postcode", e.target.value)} />
          <input aria-label="Country" placeholder="Country" disabled={disabled} className={controlClass(invalid, "sm:col-span-6")} value={a.country ?? ""} onChange={(e) => set("country", e.target.value)} />
        </div>
      );
    }
    default: {
      const type = { email: "email", phone: "tel", url: "url" }[field.type as string] ?? "text";
      return (
        <input
          {...common}
          type={field.type === "encrypted_text" ? "text" : type}
          autoComplete={field.type === "encrypted_text" ? "off" : undefined}
          maxLength={field.options.max_length}
          className={controlClass(invalid)}
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
        />
      );
    }
  }
}

function PolymorphicLookup({
  id,
  targets,
  value,
  displayName,
  onChange,
  invalid,
  describedBy,
  disabled,
}: {
  id: string;
  targets: string[];
  value: string | null;
  displayName?: string;
  onChange: (value: unknown) => void;
  invalid?: boolean;
  describedBy?: string;
  disabled?: boolean;
}) {
  const [target, setTarget] = useState(targets[0] ?? "");
  const objects = useQuery({ queryKey: ["meta", "objects"], queryFn: ({ signal }) => metaApi.objects(signal), staleTime: 300_000, enabled: targets.length > 1 });
  const readable = targets.filter((t) => !objects.data || objects.data.some((o) => o.api_name === t));
  return (
    <div className={cx(targets.length > 1 && !value && "flex gap-2")}>
      {targets.length > 1 && !value && (
        <select aria-label="Object" className={controlClass(false, "w-40 flex-none")} value={target} onChange={(e) => setTarget(e.target.value)} disabled={disabled}>
          {readable.map((t) => (
            <option key={t} value={t}>
              {objects.data?.find((o) => o.api_name === t)?.label ?? t}
            </option>
          ))}
        </select>
      )}
      <div className="flex-1">
        <Combobox
          id={id}
          value={value}
          displayName={displayName}
          onChange={(v) => onChange(v)}
          search={(q, signal) => recordsApi.lookup(target, q, signal)}
          queryKey={["lookup", target]}
          invalid={invalid}
          describedBy={describedBy}
          disabled={disabled}
        />
      </div>
    </div>
  );
}

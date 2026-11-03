import type { FieldDescribe, FilterCondition, FilterNode, ObjectDescribe } from "../../api/types";
import { PlusIcon, TrashIcon } from "../icons";
import { Button } from "../ui";
import { controlClass } from "./FieldInput";

export const RELATIVE_DATES = [
  "TODAY",
  "YESTERDAY",
  "TOMORROW",
  "THIS_WEEK",
  "LAST_WEEK",
  "NEXT_WEEK",
  "THIS_MONTH",
  "LAST_MONTH",
  "NEXT_MONTH",
  "THIS_QUARTER",
  "LAST_QUARTER",
  "NEXT_QUARTER",
  "THIS_YEAR",
  "LAST_YEAR",
  "NEXT_YEAR",
  "LAST_N_DAYS:7",
  "LAST_N_DAYS:30",
  "LAST_N_DAYS:90",
  "NEXT_N_DAYS:7",
  "NEXT_N_DAYS:30",
  "NEXT_N_DAYS:90",
];

const OPS: Record<string, { value: string; label: string }[]> = {
  text: [
    { value: "equals", label: "equals" },
    { value: "not_equals", label: "not equal to" },
    { value: "contains", label: "contains" },
    { value: "not_contains", label: "does not contain" },
    { value: "starts_with", label: "starts with" },
    { value: "is_null", label: "is blank" },
    { value: "is_not_null", label: "is not blank" },
  ],
  number: [
    { value: "equals", label: "equals" },
    { value: "not_equals", label: "not equal to" },
    { value: "gt", label: "greater than" },
    { value: "gte", label: "greater or equal" },
    { value: "lt", label: "less than" },
    { value: "lte", label: "less or equal" },
    { value: "is_null", label: "is blank" },
    { value: "is_not_null", label: "is not blank" },
  ],
  picklist: [
    { value: "in", label: "equals any of" },
    { value: "not_in", label: "not any of" },
    { value: "is_null", label: "is blank" },
    { value: "is_not_null", label: "is not blank" },
  ],
  multi: [
    { value: "includes", label: "includes" },
    { value: "excludes", label: "excludes" },
  ],
  bool: [{ value: "equals", label: "equals" }],
  id: [
    { value: "equals", label: "equals" },
    { value: "not_equals", label: "not equal to" },
    { value: "is_null", label: "is blank" },
    { value: "is_not_null", label: "is not blank" },
  ],
};

export function opsFor(f: FieldDescribe | undefined) {
  switch (f?.type) {
    case "number":
    case "currency":
    case "percent":
    case "date":
    case "datetime":
      return OPS.number!;
    case "picklist":
      return OPS.picklist!;
    case "multi_picklist":
      return OPS.multi!;
    case "checkbox":
      return OPS.bool!;
    case "lookup":
    case "master_detail":
    case "user":
    case "owner":
    case "id":
      return OPS.id!;
    default:
      return OPS.text!;
  }
}

export function isCondition(node: FilterCondition | FilterNode): node is FilterCondition {
  return "field" in node;
}

export function emptyFilter(): FilterNode {
  return { logic: "and", conditions: [] };
}

function ValueInput({
  field,
  cond,
  onChange,
}: {
  field?: FieldDescribe;
  cond: FilterCondition;
  onChange: (v: unknown) => void;
}) {
  if (cond.op === "is_null" || cond.op === "is_not_null") return null;
  if (!field) return null;
  if (field.type === "checkbox")
    return (
      <select
        aria-label="Value"
        className={controlClass(false)}
        value={String(cond.value ?? true)}
        onChange={(e) => onChange(e.target.value === "true")}
      >
        <option value="true">True</option>
        <option value="false">False</option>
      </select>
    );
  if (field.type === "picklist" || field.type === "multi_picklist") {
    const selected = new Set(
      Array.isArray(cond.value) ? (cond.value as string[]) : cond.value ? [String(cond.value)] : [],
    );
    return (
      <select
        aria-label="Values"
        multiple
        className={controlClass(false, "h-24")}
        value={[...selected]}
        onChange={(e) => onChange(Array.from(e.target.selectedOptions).map((o) => o.value))}
      >
        {(field.options.values ?? []).map((v) => (
          <option key={v.value} value={v.value}>
            {v.label}
          </option>
        ))}
      </select>
    );
  }
  if (
    field.type === "date" ||
    field.type === "datetime" ||
    field.api_name === "created_at" ||
    field.api_name === "updated_at"
  ) {
    const relative = typeof cond.value === "string" && /^[A-Z_]+(:\d+)?$/.test(cond.value);
    return (
      <div className="flex gap-1">
        <select
          aria-label="Date range"
          className={controlClass(false, "w-40")}
          value={relative ? String(cond.value) : ""}
          onChange={(e) => onChange(e.target.value || null)}
        >
          <option value="">Specific date</option>
          {RELATIVE_DATES.map((d) => (
            <option key={d} value={d}>
              {d.replace(/_/g, " ").toLowerCase()}
            </option>
          ))}
        </select>
        {!relative && (
          <input
            aria-label="Date"
            type="date"
            className={controlClass(false)}
            value={String(cond.value ?? "").slice(0, 10)}
            onChange={(e) => onChange(e.target.value)}
          />
        )}
      </div>
    );
  }
  if (["lookup", "master_detail", "user", "owner", "id"].includes(field.type)) {
    return (
      <select
        aria-label="Value"
        className={controlClass(false)}
        value={String(cond.value ?? "$me")}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="$me">Me (current user)</option>
      </select>
    );
  }
  return (
    <input
      aria-label="Value"
      type={["number", "currency", "percent"].includes(field.type) ? "number" : "text"}
      className={controlClass(false)}
      value={String(cond.value ?? "")}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}

/** Flat condition list with AND/OR logic (the API accepts nesting; the UI keeps one level). */
export function FilterBuilder({
  meta,
  value,
  onChange,
  fields,
}: {
  meta: ObjectDescribe;
  value: FilterNode;
  onChange: (value: FilterNode) => void;
  fields?: string[];
}) {
  const filterable = (fields ?? Object.keys(meta.fields)).filter((f) => meta.fields[f]?.filterable);
  const conditions = value.conditions.filter(isCondition);
  const update = (i: number, cond: FilterCondition) =>
    onChange({ ...value, conditions: conditions.map((c, j) => (j === i ? cond : c)) });
  return (
    <div className="space-y-2">
      {conditions.length > 1 && (
        <div className="flex items-center gap-2 text-sm">
          <span className="text-slate-600">Match</span>
          <select
            aria-label="Filter logic"
            className={controlClass(false, "w-auto py-1")}
            value={value.logic}
            onChange={(e) => onChange({ ...value, logic: e.target.value as "and" | "or" })}
          >
            <option value="and">all conditions (AND)</option>
            <option value="or">any condition (OR)</option>
          </select>
        </div>
      )}
      {conditions.map((cond, i) => {
        const f = meta.fields[cond.field];
        return (
          <div
            key={i}
            className="grid gap-1 rounded-md border border-slate-200 bg-white p-2 sm:grid-cols-[1fr_1fr_1.4fr_auto]"
          >
            <select
              aria-label="Field"
              className={controlClass(false)}
              value={cond.field}
              onChange={(e) =>
                update(i, {
                  field: e.target.value,
                  op: opsFor(meta.fields[e.target.value])[0]!.value,
                  value: undefined,
                })
              }
            >
              {filterable.map((api) => (
                <option key={api} value={api}>
                  {meta.fields[api]!.label}
                </option>
              ))}
            </select>
            <select
              aria-label="Operator"
              className={controlClass(false)}
              value={cond.op}
              onChange={(e) => update(i, { ...cond, op: e.target.value })}
            >
              {opsFor(f).map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <ValueInput field={f} cond={cond} onChange={(v) => update(i, { ...cond, value: v })} />
            <button
              type="button"
              aria-label="Remove condition"
              className="justify-self-end rounded p-2 text-slate-500 hover:bg-slate-100"
              onClick={() => onChange({ ...value, conditions: conditions.filter((_, j) => j !== i) })}
            >
              <TrashIcon size={16} />
            </button>
          </div>
        );
      })}
      <Button
        size="sm"
        variant="secondary"
        onClick={() => {
          const first = filterable[0] ?? "name";
          onChange({
            ...value,
            conditions: [...conditions, { field: first, op: opsFor(meta.fields[first])[0]!.value }],
          });
        }}
      >
        <PlusIcon size={14} /> Add filter
      </Button>
    </div>
  );
}

/** Drop incomplete conditions before sending to the API. */
export function cleanFilter(node: FilterNode): FilterNode | null {
  const conditions = node.conditions.filter(isCondition).filter((c) => {
    if (c.op === "is_null" || c.op === "is_not_null") return true;
    if (Array.isArray(c.value)) return c.value.length > 0;
    return c.value !== undefined && c.value !== null && c.value !== "";
  });
  return conditions.length ? { logic: node.logic, conditions } : null;
}

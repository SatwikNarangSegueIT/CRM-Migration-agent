import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { errorMessage } from "../api/client";
import { recordsApi, workspaceApi } from "../api/records";
import type { RecordData } from "../api/types";
import { FieldDisplay } from "../components/record/FieldDisplay";
import { ObjectIcon } from "../components/record/ObjectIcon";
import { RecordFormModal } from "../components/record/RecordFormModal";
import {
  CalendarIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  RecycleIcon,
  SearchIcon,
} from "../components/icons";
import { Alert, Button, EmptyState, PageHeader, Spinner, useToast } from "../components/ui";
import { cx } from "../components/ui/cx";
import { formatDateTimeValue, recordPath, TIME_ZONE, useObjectMeta } from "../lib/records";

export function SearchPage() {
  const [params] = useSearchParams();
  const q = params.get("q") ?? "";
  const results = useQuery({
    queryKey: ["search", "page", q],
    queryFn: ({ signal }) => workspaceApi.search(q, signal, 10),
    enabled: q.length > 0,
  });
  return (
    <div>
      <PageHeader
        title={`Search results for "${q}"`}
        icon={<SearchIcon size={22} className="text-brand-700" />}
        subtitle={
          results.data ? `${results.data.groups.reduce((a, g) => a + g.total, 0)} results` : undefined
        }
      />
      {results.isPending && q ? (
        <Spinner label="Searching" />
      ) : results.isError ? (
        <Alert tone="error">{errorMessage(results.error)}</Alert>
      ) : null}
      {results.data?.groups.length === 0 && (
        <EmptyState title="No results" description="Try other words, a phone number or an e-mail address." />
      )}
      <div className="space-y-4">
        {results.data?.groups.map((g) => (
          <SearchGroupCard key={g.object} group={g} />
        ))}
      </div>
    </div>
  );
}

function SearchGroupCard({
  group,
}: {
  group: {
    object: string;
    label: string;
    icon: string;
    color: string;
    total: number;
    columns: string[];
    items: RecordData[];
  };
}) {
  const meta = useObjectMeta(group.object);
  return (
    <section className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <header className="flex items-center gap-2 border-b border-slate-100 px-4 py-2.5">
        <ObjectIcon icon={group.icon} color={group.color} size={24} />
        <h2 className="font-semibold text-slate-900">
          {group.label} ({group.total})
        </h2>
      </header>
      <table className="min-w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-slate-600">
            <th scope="col" className="px-4 py-2 font-semibold">
              Name
            </th>
            {group.columns.map((c) => (
              <th key={c} scope="col" className="px-4 py-2 font-semibold">
                {meta.data?.fields[c]?.label ?? (c === "owner_id" ? "Owner" : c)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {group.items.map((r) => (
            <tr key={r.id}>
              <td className="px-4 py-2">
                <Link
                  to={recordPath(group.object, r.id)}
                  className="font-medium text-brand-700 hover:underline"
                >
                  {r.name}
                </Link>
              </td>
              {group.columns.map((c) => (
                <td key={c} className="px-4 py-2">
                  <FieldDisplay field={meta.data?.fields[c]} record={r} apiName={c} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function startOfWeek(d: Date): Date {
  const x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  x.setDate(x.getDate() - ((x.getDay() + 6) % 7));
  return x;
}
const dayKey = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

export function CalendarPage() {
  const [view, setView] = useState<"month" | "week" | "day">("month");
  const [anchor, setAnchor] = useState(() => new Date());
  const [mine, setMine] = useState(true);
  const [creating, setCreating] = useState<string | null>(null);
  const eventMeta = useObjectMeta("event");
  const toast = useToast();
  const queryClient = useQueryClient();
  const { start, days } = useMemo(() => {
    if (view === "day")
      return { start: new Date(anchor.getFullYear(), anchor.getMonth(), anchor.getDate()), days: 1 };
    if (view === "week") return { start: startOfWeek(anchor), days: 7 };
    const first = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
    return { start: startOfWeek(first), days: 42 };
  }, [view, anchor]);
  const end = new Date(start);
  end.setDate(end.getDate() + days);
  const data = useQuery({
    queryKey: ["calendar", start.toISOString(), days, mine],
    queryFn: ({ signal }) => workspaceApi.calendar(start.toISOString(), end.toISOString(), mine, signal),
  });
  const byDay = new Map<string, { record: RecordData; kind: "event" | "task"; time: string }[]>();
  for (const e of data.data?.events ?? []) {
    const s = new Date(String(e.fields.start_at));
    const k = dayKey(s);
    byDay.set(k, [
      ...(byDay.get(k) ?? []),
      {
        record: e,
        kind: "event",
        time: e.fields.all_day
          ? "All day"
          : s.toLocaleTimeString("en-AU", { hour: "numeric", minute: "2-digit", timeZone: TIME_ZONE }),
      },
    ]);
  }
  for (const t of data.data?.tasks ?? []) {
    const k = String(t.fields.due_date);
    byDay.set(k, [...(byDay.get(k) ?? []), { record: t, kind: "task", time: "Task" }]);
  }
  function shift(n: number) {
    const d = new Date(anchor);
    if (view === "month") d.setMonth(d.getMonth() + n);
    else d.setDate(d.getDate() + n * (view === "week" ? 7 : 1));
    setAnchor(d);
  }
  const title =
    view === "month"
      ? anchor.toLocaleDateString("en-AU", { month: "long", year: "numeric" })
      : `${start.toLocaleDateString("en-AU", { day: "numeric", month: "short" })} – ${new Date(end.getTime() - 86400000).toLocaleDateString("en-AU", { day: "numeric", month: "short", year: "numeric" })}`;
  const cells = Array.from({ length: days }, (_, i) => {
    const d = new Date(start);
    d.setDate(d.getDate() + i);
    return d;
  });
  const todayKey = dayKey(new Date());
  return (
    <div>
      <PageHeader
        title={title}
        icon={<CalendarIcon size={22} className="text-brand-700" />}
        actions={
          <>
            <div
              className="inline-flex overflow-hidden rounded-md border border-slate-300 bg-white"
              role="group"
              aria-label="Calendar view"
            >
              {(["day", "week", "month"] as const).map((v) => (
                <button
                  key={v}
                  type="button"
                  aria-pressed={view === v}
                  className={cx(
                    "px-3 py-1.5 text-sm capitalize",
                    view === v ? "bg-brand-50 font-semibold text-brand-700" : "text-slate-700",
                  )}
                  onClick={() => setView(v)}
                >
                  {v}
                </button>
              ))}
            </div>
            <Button variant="secondary" size="sm" onClick={() => shift(-1)} aria-label="Previous">
              <ChevronLeftIcon size={16} />
            </Button>
            <Button variant="secondary" size="sm" onClick={() => setAnchor(new Date())}>
              Today
            </Button>
            <Button variant="secondary" size="sm" onClick={() => shift(1)} aria-label="Next">
              <ChevronRightIcon size={16} />
            </Button>
            <label className="flex items-center gap-1.5 text-sm text-slate-700">
              <input type="checkbox" checked={mine} onChange={(e) => setMine(e.target.checked)} /> Only mine
            </label>
          </>
        }
      />
      {data.isError && <Alert tone="error">{errorMessage(data.error)}</Alert>}
      <div
        className={cx(
          "grid overflow-hidden rounded-lg border border-slate-300 bg-slate-300",
          view === "day" ? "grid-cols-1" : "grid-cols-7",
        )}
        style={{ gap: 1 }}
      >
        {view !== "day" &&
          ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
            <div key={d} className="bg-slate-50 px-2 py-1 text-xs font-semibold text-slate-600">
              {d}
            </div>
          ))}
        {cells.map((d) => {
          const k = dayKey(d);
          const items = (byDay.get(k) ?? []).sort((a, b) => a.time.localeCompare(b.time));
          const outside = view === "month" && d.getMonth() !== anchor.getMonth();
          return (
            <div
              key={k}
              className={cx(
                "min-h-[6.5rem] bg-white p-1.5",
                outside && "bg-slate-50 text-slate-400",
                view !== "month" && "min-h-[20rem]",
              )}
            >
              <div className="flex items-center justify-between">
                <span
                  className={cx(
                    "text-xs",
                    k === todayKey && "rounded-full bg-brand-700 px-1.5 font-semibold text-white",
                  )}
                >
                  {d.getDate()}
                </span>
                {eventMeta.data?.access.create && (
                  <button
                    type="button"
                    aria-label={`New event on ${k}`}
                    className="rounded px-1 text-xs text-slate-400 hover:bg-slate-100 hover:text-brand-700"
                    onClick={() => setCreating(k)}
                  >
                    +
                  </button>
                )}
              </div>
              <ul className="mt-1 space-y-0.5">
                {items.map(({ record, kind, time }) => (
                  <li key={record.id}>
                    <Link
                      to={recordPath(kind, record.id)}
                      className={cx(
                        "block truncate rounded px-1 py-0.5 text-xs",
                        kind === "event"
                          ? "bg-cyan-50 text-cyan-900 hover:bg-cyan-100"
                          : "bg-emerald-50 text-emerald-900 hover:bg-emerald-100",
                      )}
                      title={`${time} ${record.name}`}
                    >
                      <span className="font-medium">{time}</span> {record.name}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
      {creating && eventMeta.data && (
        <RecordFormModal
          meta={eventMeta.data}
          record={null}
          defaults={{
            start_at: new Date(`${creating}T09:00:00`).toISOString(),
            end_at: new Date(`${creating}T10:00:00`).toISOString(),
          }}
          open
          onClose={() => setCreating(null)}
          onSaved={() => {
            setCreating(null);
            toast.show("Event created.");
            void queryClient.invalidateQueries({ queryKey: ["calendar"] });
          }}
        />
      )}
    </div>
  );
}

export function RecycleBinPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const items = useQuery({
    queryKey: ["recycle-bin"],
    queryFn: ({ signal }) => workspaceApi.recycleBin(signal),
  });
  const restore = useMutation({
    mutationFn: (r: { object: string; id: string }) => recordsApi.restore(r.object, r.id),
    onSuccess: (r) => {
      toast.show(`"${r.name}" restored.`);
      void queryClient.invalidateQueries({ queryKey: ["recycle-bin"] });
      void queryClient.invalidateQueries({ queryKey: ["records"] });
    },
    onError: (e) => toast.show(errorMessage(e), "error"),
  });
  return (
    <div>
      <PageHeader
        title="Recycle Bin"
        subtitle="Deleted records are kept for 30 days, then removed permanently."
        icon={<RecycleIcon size={22} className="text-brand-700" />}
      />
      {items.isPending ? (
        <Spinner label="Loading" />
      ) : items.isError ? (
        <Alert tone="error">{errorMessage(items.error)}</Alert>
      ) : items.data.length === 0 ? (
        <EmptyState
          title="The recycle bin is empty"
          description="Records you delete appear here."
          icon={<RecycleIcon size={36} />}
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-300 bg-white">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-600">
                <th scope="col" className="px-4 py-2">
                  Name
                </th>
                <th scope="col" className="px-4 py-2">
                  Type
                </th>
                <th scope="col" className="px-4 py-2">
                  Deleted
                </th>
                <th scope="col" className="px-4 py-2">
                  Removed permanently
                </th>
                <th scope="col" className="px-4 py-2">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.data.map((r) => (
                <tr key={r.id}>
                  <td className="px-4 py-2">
                    <Link to={recordPath(r.object, r.id)} className="text-brand-700 hover:underline">
                      {r.name}
                    </Link>
                  </td>
                  <td className="px-4 py-2">{r.object_label}</td>
                  <td className="px-4 py-2">{formatDateTimeValue(r.deleted_at)}</td>
                  <td className="px-4 py-2">{formatDateTimeValue(r.purge_at)}</td>
                  <td className="px-4 py-2 text-right">
                    <Button
                      size="sm"
                      variant="secondary"
                      loading={restore.isPending && restore.variables?.id === r.id}
                      onClick={() => restore.mutate(r)}
                    >
                      Restore
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

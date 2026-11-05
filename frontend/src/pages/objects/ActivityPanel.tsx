import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "../../api/client";
import { fileUrl, recordsApi } from "../../api/records";
import type { ObjectDescribe, RecordData } from "../../api/types";
import { ObjectIcon } from "../../components/record/ObjectIcon";
import { RecordFormModal } from "../../components/record/RecordFormModal";
import { CheckIcon } from "../../components/icons";
import { Spinner, useToast } from "../../components/ui";
import { cx } from "../../components/ui/cx";
import { formatDate, formatDateTimeValue, recordPath, today, useObjectMeta } from "../../lib/records";

type Kind = "task" | "event" | "call" | "note";

type Item = { record: RecordData; object: string; when: string; done: boolean };

/** Activity timeline: quick entry for tasks, events, calls and notes; upcoming & overdue, then past activity. */
export function ActivityPanel({ meta, record }: { meta: ObjectDescribe; record: RecordData }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const allowed = new Map(meta.activity_objects.map((a) => [a.object, a.can_create]));
  const [composer, setComposer] = useState<Kind | null>(null);
  const taskMeta = useObjectMeta(allowed.has("task") ? "task" : undefined);
  const eventMeta = useObjectMeta(allowed.has("event") ? "event" : undefined);
  const noteMeta = useObjectMeta(allowed.has("note") ? "note" : undefined);
  const data = useQuery({
    queryKey: ["activities", meta.api_name, record.id],
    queryFn: ({ signal }) => recordsApi.activities(meta.api_name, record.id, signal),
  });
  const complete = useMutation({
    mutationFn: (task: RecordData) =>
      recordsApi.update("task", task.id, { version: task.version, fields: { status: "Completed" } }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["activities"] }),
    onError: (e) => toast.show(errorMessage(e), "error"),
  });

  const items: Item[] = [];
  for (const t of data.data?.task ?? [])
    items.push({
      record: t,
      object: "task",
      when: String(t.fields.due_date ?? t.created_at),
      done: t.fields.status === "Completed",
    });
  for (const e of data.data?.event ?? [])
    items.push({
      record: e,
      object: "event",
      when: String(e.fields.start_at ?? e.created_at),
      done: new Date(String(e.fields.end_at ?? e.fields.start_at)) < new Date(),
    });
  for (const n of data.data?.note ?? [])
    items.push({ record: n, object: "note", when: n.created_at, done: true });
  for (const f of data.data?.file ?? [])
    items.push({ record: f, object: "file", when: f.created_at, done: true });
  const upcoming = items.filter((i) => !i.done).sort((a, b) => a.when.localeCompare(b.when));
  const past = items.filter((i) => i.done).sort((a, b) => b.when.localeCompare(a.when));

  const composerMeta =
    composer === "event" ? eventMeta.data : composer === "note" ? noteMeta.data : taskMeta.data;
  const composerDefaults: Record<string, unknown> = { related_to: record.id };
  if (composer === "call")
    Object.assign(composerDefaults, { type: "Call", status: "Completed", due_date: today(), name: "Call" });
  if (composer === "task") Object.assign(composerDefaults, { due_date: today() });
  if (composer === "event") {
    const start = new Date();
    start.setMinutes(0, 0, 0);
    start.setHours(start.getHours() + 1);
    Object.assign(composerDefaults, {
      start_at: start.toISOString(),
      end_at: new Date(start.getTime() + 3600_000).toISOString(),
    });
  }
  if ((meta.api_name === "contact" || meta.api_name === "lead") && composer !== "note")
    composerDefaults.who = record.id;

  const buttons: { kind: Kind; label: string; object: string }[] = [
    { kind: "call", label: "Log a Call", object: "task" },
    { kind: "task", label: "New Task", object: "task" },
    { kind: "event", label: "New Event", object: "event" },
    { kind: "note", label: "New Note", object: "note" },
  ];

  return (
    <section aria-label="Activity" className="rounded-xl border border-slate-200/80 bg-white shadow-card">
      <header className="border-b border-slate-100 px-4 py-2.5">
        <h3 className="text-sm font-semibold text-slate-900">Activity</h3>
        <div className="mt-2 flex flex-wrap gap-1">
          {buttons
            .filter((b) => allowed.get(b.object))
            .map((b) => (
              <button
                key={b.kind}
                type="button"
                className="rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-brand-700 hover:bg-slate-50"
                onClick={() => setComposer(b.kind)}
              >
                {b.label}
              </button>
            ))}
        </div>
      </header>
      {data.isPending ? (
        <div className="p-4">
          <Spinner label="Loading activity" />
        </div>
      ) : (
        <div className="space-y-3 p-4">
          <Timeline
            title="Upcoming & Overdue"
            items={upcoming}
            onComplete={(r) => complete.mutate(r)}
            empty="No upcoming activities."
          />
          <Timeline title="Past Activity" items={past} empty="No past activity." />
        </div>
      )}
      {composer && composerMeta && (
        <RecordFormModal
          key={composer}
          meta={composerMeta}
          record={null}
          defaults={composerDefaults}
          defaultNames={{ related_to: record.name, who: record.name }}
          open
          onClose={() => setComposer(null)}
          onSaved={() => {
            setComposer(null);
            toast.show("Activity saved.");
            void queryClient.invalidateQueries({ queryKey: ["activities"] });
          }}
        />
      )}
    </section>
  );
}

function Timeline({
  title,
  items,
  empty,
  onComplete,
}: {
  title: string;
  items: Item[];
  empty: string;
  onComplete?: (r: RecordData) => void;
}) {
  const icons: Record<string, { icon: string; color: string }> = {
    task: { icon: "task", color: "#22c55e" },
    event: { icon: "event", color: "#06b6d4" },
    note: { icon: "note", color: "#eab308" },
    file: { icon: "file", color: "#64748b" },
  };
  const now = new Date().toISOString().slice(0, 10);
  return (
    <div>
      <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</h4>
      {items.length === 0 ? (
        <p className="text-sm text-slate-500">{empty}</p>
      ) : (
        <ol className="space-y-2">
          {items.map(({ record: r, object, when }) => {
            const overdue =
              object === "task" &&
              r.fields.status !== "Completed" &&
              String(r.fields.due_date ?? "9999") < now;
            const meta = icons[object]!;
            return (
              <li key={r.id} className="flex gap-2 text-sm">
                <ObjectIcon icon={meta.icon} color={meta.color} size={24} className="mt-0.5" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    {object === "file" ? (
                      <a
                        href={fileUrl(r.id, true)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="truncate font-medium text-brand-700 hover:underline"
                      >
                        {r.name}
                      </a>
                    ) : (
                      <Link
                        to={recordPath(object, r.id)}
                        className="truncate font-medium text-brand-700 hover:underline"
                      >
                        {r.name}
                      </Link>
                    )}
                    <span
                      className={cx(
                        "flex-none text-xs",
                        overdue ? "font-semibold text-red-700" : "text-slate-500",
                      )}
                    >
                      {object === "event"
                        ? formatDateTimeValue(when)
                        : object === "task"
                          ? formatDate(when)
                          : formatDateTimeValue(when)}
                    </span>
                  </div>
                  {object === "note" && r.fields.body ? (
                    <p className="line-clamp-3 whitespace-pre-wrap text-xs text-slate-600">
                      {String(r.fields.body)}
                    </p>
                  ) : null}
                  {object === "task" && (
                    <p className="text-xs text-slate-500">
                      {String(r.fields.status ?? "")} · {r.owner?.name}
                      {onComplete && r.access.edit && r.fields.status !== "Completed" && (
                        <button
                          type="button"
                          className="ml-2 inline-flex items-center gap-0.5 text-brand-700 hover:underline"
                          onClick={() => onComplete(r)}
                        >
                          <CheckIcon size={12} /> Complete
                        </button>
                      )}
                    </p>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}

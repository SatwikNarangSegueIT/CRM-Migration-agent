import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { analyticsApi, type ChartType, type Report, type ReportDefinition } from "../../api/analytics";
import { API_BASE, ApiError, errorMessage } from "../../api/client";
import type { FilterNode, ObjectDescribe } from "../../api/types";
import { useAuth } from "../../auth/context";
import { Chart, ResultTable } from "../../components/charts/Chart";
import { cleanFilter, emptyFilter, FilterBuilder } from "../../components/record/FilterBuilder";
import { controlClass } from "../../components/record/FieldInput";
import { ChartIcon, CloseIcon, DownloadIcon, PlusIcon, RefreshIcon } from "../../components/icons";
import {
  Alert,
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  FormField,
  Input,
  ListSearch,
  PageHeader,
  Spinner,
  useToast,
} from "../../components/ui";
import { Modal } from "../../components/ui/Modal";
import { formatDateTimeValue, useObjectMeta, useObjects } from "../../lib/records";
import { NotFoundPage } from "../NotFoundPage";

export function ReportsPage() {
  const { object } = useAuth();
  const [q, setQ] = useState("");
  const [folder, setFolder] = useState<string>("all");
  const reports = useQuery({
    queryKey: ["reports", q],
    queryFn: ({ signal }) => analyticsApi.reports(q || undefined, signal),
    placeholderData: keepPreviousData,
  });
  const folders = useMemo(
    () => [...new Set((reports.data ?? []).map((r) => r.folder_name))].sort(),
    [reports.data],
  );
  const shown = (reports.data ?? []).filter((r) => folder === "all" || r.folder_name === folder);
  return (
    <div>
      <PageHeader
        title="Reports"
        icon={<ChartIcon size={22} className="text-brand-700" />}
        actions={
          <>
            <ListSearch initial={q} onSearch={setQ} label="Search reports" />
            {object("report").create && (
              <Link
                to="/reports/new"
                className="inline-flex items-center gap-2 rounded-md bg-brand-700 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-brand-800"
              >
                <PlusIcon size={16} /> New Report
              </Link>
            )}
          </>
        }
      />
      <div className="grid gap-4 md:grid-cols-[14rem_1fr]">
        <nav
          aria-label="Folders"
          className="rounded-lg border border-slate-200 bg-white p-2 text-sm shadow-sm"
        >
          {["all", ...folders].map((f) => (
            <button
              key={f}
              type="button"
              aria-current={folder === f ? "true" : undefined}
              className={`block w-full rounded px-3 py-2 text-left ${folder === f ? "bg-brand-50 font-semibold text-brand-700" : "hover:bg-slate-50"}`}
              onClick={() => setFolder(f)}
            >
              {f === "all" ? "All Reports" : f}
            </button>
          ))}
          <Link
            to="/dashboards"
            className="mt-2 block border-t border-slate-100 px-3 py-2 text-brand-700 hover:underline"
          >
            Dashboards →
          </Link>
        </nav>
        <div className="overflow-x-auto rounded-lg border border-slate-300 bg-white">
          {reports.isPending ? (
            <div className="p-6">
              <Spinner label="Loading reports" />
            </div>
          ) : reports.isError ? (
            <Alert tone="error">{errorMessage(reports.error)}</Alert>
          ) : shown.length === 0 ? (
            <EmptyState
              title="No reports"
              description="Create a report to analyse your data."
              icon={<ChartIcon size={36} />}
              action={object("report").create ? { label: "New Report", to: "/reports/new" } : undefined}
            />
          ) : (
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-600">
                  <th scope="col" className="px-4 py-2">
                    Report name
                  </th>
                  <th scope="col" className="px-4 py-2">
                    Description
                  </th>
                  <th scope="col" className="px-4 py-2">
                    Object
                  </th>
                  <th scope="col" className="px-4 py-2">
                    Folder
                  </th>
                  <th scope="col" className="px-4 py-2">
                    Last run
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {shown.map((r) => (
                  <tr key={r.id}>
                    <td className="px-4 py-2">
                      <Link to={`/reports/${r.id}`} className="font-medium text-brand-700 hover:underline">
                        {r.name}
                      </Link>
                    </td>
                    <td className="max-w-md truncate px-4 py-2 text-slate-600">{r.description}</td>
                    <td className="px-4 py-2">{r.object_label}</td>
                    <td className="px-4 py-2">{r.folder_name}</td>
                    <td className="px-4 py-2">{formatDateTimeValue(r.last_run_at) || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

export function ReportPage() {
  const { id = "" } = useParams();
  const { can } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const report = useQuery({
    queryKey: ["report", id],
    queryFn: ({ signal }) => analyticsApi.report(id, signal),
  });
  const result = useQuery({
    queryKey: ["report-run", id],
    queryFn: ({ signal }) => analyticsApi.run(id, undefined, signal),
    enabled: report.isSuccess,
  });
  const [editing, setEditing] = useState(false);
  const [scheduling, setScheduling] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const remove = useMutation({
    mutationFn: () => analyticsApi.remove(id),
    onSuccess: () => {
      toast.show("Report deleted.");
      void queryClient.invalidateQueries({ queryKey: ["reports"] });
      navigate("/reports");
    },
    onError: (e) => toast.show(errorMessage(e), "error"),
  });
  if (report.isPending) return <Spinner label="Loading report" />;
  if (report.isError)
    return report.error instanceof ApiError && report.error.status === 404 ? (
      <NotFoundPage />
    ) : (
      <Alert tone="error">{errorMessage(report.error)}</Alert>
    );
  const r = report.data;
  if (editing)
    return (
      <ReportBuilder
        initial={r}
        onDone={() => {
          setEditing(false);
          void queryClient.invalidateQueries({ queryKey: ["report-run", id] });
          void report.refetch();
        }}
      />
    );
  const chartType = r.definition.chart?.type;
  return (
    <div className="space-y-3">
      <PageHeader
        title={r.name}
        subtitle={
          <span>
            {r.object_label} · {r.folder_name}
            {result.data ? ` · Run ${formatDateTimeValue(result.data.run_at)}` : ""}
          </span>
        }
        breadcrumbs={[{ label: "Reports", to: "/reports" }, { label: r.name }]}
        icon={<ChartIcon size={22} className="text-brand-700" />}
        actions={
          <>
            <Button variant="secondary" onClick={() => void result.refetch()} loading={result.isFetching}>
              <RefreshIcon size={16} /> Refresh
            </Button>
            {can("export_data") && (
              <a
                href={`${API_BASE}/reports/${id}/export.csv`}
                className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50"
              >
                <DownloadIcon size={16} /> Export
              </a>
            )}
            <Button variant="secondary" onClick={() => setScheduling(true)}>
              Subscribe
            </Button>
            {r.can_edit ? (
              <Button onClick={() => setEditing(true)}>Edit</Button>
            ) : (
              <Button variant="secondary" onClick={() => navigate("/reports/new", { state: { copyOf: r } })}>
                Save As
              </Button>
            )}
            {r.can_edit && !r.key && (
              <Button variant="danger" onClick={() => setDeleting(true)}>
                Delete
              </Button>
            )}
          </>
        }
      />
      {r.description && <p className="text-sm text-slate-600">{r.description}</p>}
      {result.isPending ? (
        <Spinner label="Running report" />
      ) : result.isError ? (
        <Alert tone="error">{errorMessage(result.error)}</Alert>
      ) : (
        <>
          {result.data.format !== "tabular" && chartType && chartType !== "table" && (
            <Card>
              <Chart result={result.data} type={chartType} title={r.name} />
            </Card>
          )}
          <Card>
            <ResultTable result={result.data} />
            {"truncated" in result.data && result.data.truncated && (
              <p className="mt-2 text-xs text-amber-700">
                Showing the first rows only; add filters or export for everything.
              </p>
            )}
          </Card>
        </>
      )}
      {scheduling && <ScheduleDialog reportId={id} onClose={() => setScheduling(false)} />}
      <ConfirmDialog
        open={deleting}
        title="Delete report?"
        tone="danger"
        confirmLabel="Delete"
        loading={remove.isPending}
        onCancel={() => setDeleting(false)}
        onConfirm={() => remove.mutate()}
      />
    </div>
  );
}

function ScheduleDialog({ reportId, onClose }: { reportId: string; onClose: () => void }) {
  const { can } = useAuth();
  const queryClient = useQueryClient();
  const schedules = useQuery({
    queryKey: ["schedules", reportId],
    queryFn: ({ signal }) => analyticsApi.schedules(reportId, signal),
  });
  const [frequency, setFrequency] = useState("weekly");
  const [recipients, setRecipients] = useState("");
  const add = useMutation({
    mutationFn: () =>
      analyticsApi.schedule(reportId, { frequency, recipients: recipients.split(/[,\s]+/).filter(Boolean) }),
    onSuccess: () => {
      setRecipients("");
      void queryClient.invalidateQueries({ queryKey: ["schedules", reportId] });
    },
  });
  const remove = useMutation({
    mutationFn: (sid: string) => analyticsApi.unschedule(reportId, sid),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["schedules", reportId] }),
  });
  return (
    <Modal
      open
      onClose={onClose}
      title="Subscribe to this report"
      size="sm"
      footer={
        <Button variant="secondary" onClick={onClose}>
          Done
        </Button>
      }
    >
      <div className="space-y-3 text-sm">
        {add.isError && <Alert tone="error">{errorMessage(add.error)}</Alert>}
        <ul className="divide-y divide-slate-100 rounded border border-slate-200">
          {(schedules.data ?? []).map((s) => (
            <li key={s.id} className="flex items-center justify-between px-3 py-2">
              <span className="capitalize">
                {s.frequency} · next {formatDateTimeValue(s.next_run_at)}
                {s.recipients.length ? ` · ${s.recipients.join(", ")}` : ""}
              </span>
              {s.is_mine && (
                <button
                  type="button"
                  aria-label="Remove schedule"
                  className="rounded p-1 hover:bg-slate-100"
                  onClick={() => remove.mutate(s.id)}
                >
                  <CloseIcon size={14} />
                </button>
              )}
            </li>
          ))}
          {schedules.data?.length === 0 && (
            <li className="px-3 py-2 text-slate-500">No subscriptions yet.</li>
          )}
        </ul>
        <div className="grid gap-2">
          <select
            aria-label="Frequency"
            className={controlClass(false)}
            value={frequency}
            onChange={(e) => setFrequency(e.target.value)}
          >
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
          {can("manage_public_reports") && (
            <Input
              aria-label="Other recipients"
              placeholder="Other recipients (e-mails, comma separated)"
              value={recipients}
              onChange={(e) => setRecipients(e.target.value)}
            />
          )}
          <Button onClick={() => add.mutate()} loading={add.isPending}>
            Add subscription
          </Button>
        </div>
      </div>
    </Modal>
  );
}

const CHARTS: { value: ChartType; label: string }[] = [
  { value: "table", label: "None (table)" },
  { value: "column", label: "Column" },
  { value: "bar", label: "Bar" },
  { value: "line", label: "Line" },
  { value: "donut", label: "Donut" },
  { value: "funnel", label: "Funnel" },
  { value: "kpi", label: "KPI (total)" },
];

export function ReportBuilder({ initial, onDone }: { initial?: Report; onDone?: () => void }) {
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();
  const objects = useObjects();
  const folders = useQuery({
    queryKey: ["report-folders"],
    queryFn: ({ signal }) => analyticsApi.folders(signal),
  });
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [folderId, setFolderId] = useState<string>(initial?.folder_id ?? "");
  const [object, setObject] = useState(initial?.object_api_name ?? "opportunity");
  const [def, setDef] = useState<ReportDefinition>(
    initial?.definition ?? {
      format: "summary",
      group_by: ["stage"],
      aggregates: [{ op: "count" }],
      chart: { type: "column" },
    },
  );
  const [filter, setFilter] = useState<FilterNode>(() =>
    def.filters && "conditions" in def.filters ? def.filters : emptyFilter(),
  );
  const meta = useObjectMeta(object);
  const columns = useQuery({
    queryKey: ["report-columns", object],
    queryFn: ({ signal }) => analyticsApi.columns(object, signal),
  });
  const body = {
    name: name || "Preview",
    description: description || null,
    folder_id: folderId || null,
    object_api_name: object,
    definition: { ...def, filters: cleanFilter(filter) },
  };
  const [debounced, setDebounced] = useState(JSON.stringify(body));
  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(JSON.stringify(body)), 400);
    return () => window.clearTimeout(t);
  });
  const preview = useQuery({
    queryKey: ["report-preview", debounced],
    queryFn: ({ signal }) => analyticsApi.preview(JSON.parse(debounced), signal),
    retry: false,
    placeholderData: keepPreviousData,
  });
  const save = useMutation({
    mutationFn: () =>
      initial?.can_edit
        ? analyticsApi.update(initial.id, { ...body, name })
        : analyticsApi.create({ ...body, name }),
    onSuccess: (r) => {
      toast.show(`Report "${r.name}" saved.`);
      void queryClient.invalidateQueries({ queryKey: ["reports"] });
      if (onDone) onDone();
      else navigate(`/reports/${r.id}`);
    },
  });
  const cols = columns.data ?? [];
  const numeric = cols.filter((c) => ["number", "currency", "percent"].includes(c.type));
  const groupable = cols.filter(
    (c) => !["long_text", "address", "encrypted_text", "multi_picklist"].includes(c.type),
  );
  const dateCols = cols.filter((c) => c.type === "date" || c.type === "datetime");
  const set = (patch: Partial<ReportDefinition>) => setDef((d) => ({ ...d, ...patch }));
  const reportable = (objects.data ?? []).filter((o) => o.allow_reports);

  return (
    <div className="space-y-3">
      <PageHeader
        title={initial ? `Edit report: ${initial.name}` : "New Report"}
        breadcrumbs={[{ label: "Reports", to: "/reports" }, { label: initial ? initial.name : "New" }]}
        actions={
          <>
            <Button variant="secondary" onClick={() => (onDone ? onDone() : navigate("/reports"))}>
              Cancel
            </Button>
            <Button onClick={() => save.mutate()} loading={save.isPending} disabled={!name.trim()}>
              Save
            </Button>
          </>
        }
      />
      {save.isError && <Alert tone="error">{errorMessage(save.error)}</Alert>}
      <div className="grid gap-3 lg:grid-cols-[22rem_1fr]">
        <Card>
          <div className="space-y-4 text-sm">
            <FormField label="Report name" required>
              {({ id }) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} />}
            </FormField>
            <FormField label="Description">
              {({ id }) => (
                <Input id={id} value={description} onChange={(e) => setDescription(e.target.value)} />
              )}
            </FormField>
            <FormField label="Folder">
              {({ id }) => (
                <select
                  id={id}
                  className={controlClass(false)}
                  value={folderId}
                  onChange={(e) => setFolderId(e.target.value)}
                >
                  <option value="">Private reports</option>
                  {(folders.data ?? [])
                    .filter((f) => f.can_edit)
                    .map((f) => (
                      <option key={f.id} value={f.id}>
                        {f.name}
                      </option>
                    ))}
                </select>
              )}
            </FormField>
            <FormField label="Report type (object)">
              {({ id }) => (
                <select
                  id={id}
                  className={controlClass(false)}
                  value={object}
                  disabled={Boolean(initial)}
                  onChange={(e) => {
                    setObject(e.target.value);
                    setDef({ format: "tabular", columns: ["name"], aggregates: [{ op: "count" }] });
                    setFilter(emptyFilter());
                  }}
                >
                  {reportable.map((o) => (
                    <option key={o.api_name} value={o.api_name}>
                      {o.plural_label}
                    </option>
                  ))}
                </select>
              )}
            </FormField>
            <FormField label="Format">
              {({ id }) => (
                <select
                  id={id}
                  className={controlClass(false)}
                  value={def.format}
                  onChange={(e) =>
                    set({
                      format: e.target.value as ReportDefinition["format"],
                      group_by:
                        e.target.value === "tabular"
                          ? []
                          : def.group_by?.length
                            ? def.group_by
                            : [groupable[0]?.key ?? "owner_id"],
                      group_columns: e.target.value === "matrix" ? [groupable[1]?.key ?? "owner_id"] : [],
                    })
                  }
                >
                  <option value="tabular">Tabular (rows)</option>
                  <option value="summary">Summary (grouped)</option>
                  <option value="matrix">Matrix (rows × columns)</option>
                </select>
              )}
            </FormField>
            <FormField label="Show">
              {({ id }) => (
                <select
                  id={id}
                  className={controlClass(false)}
                  value={def.scope ?? "all"}
                  onChange={(e) => set({ scope: e.target.value as ReportDefinition["scope"] })}
                >
                  <option value="all">All records I can see</option>
                  <option value="mine">My records</option>
                  <option value="team">My team's records</option>
                </select>
              )}
            </FormField>
            {def.format === "tabular" ? (
              <ColumnPicker
                label="Columns"
                options={cols}
                value={def.columns ?? []}
                onChange={(columns) => set({ columns })}
              />
            ) : (
              <>
                <ColumnPicker
                  label="Group rows by (max 2)"
                  options={[
                    ...groupable,
                    ...dateCols.map((c) => ({
                      ...c,
                      key: `age:${c.key}`,
                      label: `${c.label} (age buckets)`,
                    })),
                  ]}
                  value={def.group_by ?? []}
                  max={2}
                  onChange={(group_by) => set({ group_by })}
                />
                {def.format === "matrix" && (
                  <ColumnPicker
                    label="Group columns by"
                    options={groupable}
                    value={def.group_columns ?? []}
                    max={1}
                    onChange={(group_columns) => set({ group_columns })}
                  />
                )}
                {[...(def.group_by ?? []), ...(def.group_columns ?? [])]
                  .filter((g) => dateCols.some((c) => c.key === g))
                  .map((g) => (
                    <FormField key={g} label={`Group ${cols.find((c) => c.key === g)?.label} by`}>
                      {({ id }) => (
                        <select
                          id={id}
                          className={controlClass(false)}
                          value={def.date_granularity?.[g] ?? ""}
                          onChange={(e) =>
                            set({
                              date_granularity: {
                                ...def.date_granularity,
                                ...(e.target.value ? { [g]: e.target.value as "month" } : {}),
                              },
                            })
                          }
                        >
                          <option value="">Exact date</option>
                          <option value="day">Day</option>
                          <option value="week">Week</option>
                          <option value="month">Month</option>
                          <option value="quarter">Quarter</option>
                          <option value="year">Year</option>
                        </select>
                      )}
                    </FormField>
                  ))}
              </>
            )}
            <fieldset>
              <legend className="text-sm font-medium text-slate-700">Summaries</legend>
              <div className="mt-1 space-y-1">
                {(def.aggregates ?? [{ op: "count" }]).map((a, i) => (
                  <div key={i} className="flex gap-1">
                    <select
                      aria-label="Aggregate"
                      className={controlClass(false, "w-24")}
                      value={a.op}
                      onChange={(e) =>
                        set({
                          aggregates: (def.aggregates ?? []).map((x, j) =>
                            j === i
                              ? {
                                  op: e.target.value as "sum",
                                  field:
                                    e.target.value === "count" ? undefined : (x.field ?? numeric[0]?.key),
                                }
                              : x,
                          ),
                        })
                      }
                    >
                      <option value="count">Count</option>
                      <option value="sum">Sum</option>
                      <option value="avg">Average</option>
                      <option value="min">Min</option>
                      <option value="max">Max</option>
                    </select>
                    {a.op !== "count" && (
                      <select
                        aria-label="Field"
                        className={controlClass(false)}
                        value={a.field ?? ""}
                        onChange={(e) =>
                          set({
                            aggregates: (def.aggregates ?? []).map((x, j) =>
                              j === i ? { ...x, field: e.target.value } : x,
                            ),
                          })
                        }
                      >
                        {(a.op === "sum" || a.op === "avg" ? numeric : cols).map((c) => (
                          <option key={c.key} value={c.key}>
                            {c.label}
                          </option>
                        ))}
                      </select>
                    )}
                    <button
                      type="button"
                      aria-label="Remove summary"
                      className="rounded px-1 text-slate-500 hover:bg-slate-100"
                      onClick={() => set({ aggregates: (def.aggregates ?? []).filter((_, j) => j !== i) })}
                    >
                      <CloseIcon size={14} />
                    </button>
                  </div>
                ))}
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() =>
                    set({
                      aggregates: [
                        ...(def.aggregates ?? []),
                        numeric[0] ? { op: "sum", field: numeric[0].key } : { op: "count" },
                      ],
                    })
                  }
                >
                  <PlusIcon size={14} /> Add summary
                </Button>
              </div>
            </fieldset>
            {def.format !== "tabular" && (
              <FormField label="Chart">
                {({ id }) => (
                  <select
                    id={id}
                    className={controlClass(false)}
                    value={def.chart?.type ?? "table"}
                    onChange={(e) => set({ chart: { type: e.target.value as ChartType } })}
                  >
                    {CHARTS.map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                )}
              </FormField>
            )}
          </div>
        </Card>
        <div className="space-y-3">
          <Card>
            <h2 className="mb-2 text-sm font-semibold text-slate-900">Filters</h2>
            {meta.data ? (
              <FilterBuilder meta={meta.data as ObjectDescribe} value={filter} onChange={setFilter} />
            ) : (
              <Spinner label="Loading fields" />
            )}
          </Card>
          <Card>
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-900">Preview</h2>
              {preview.isFetching && <Badge tone="blue">Updating…</Badge>}
            </div>
            {preview.isError ? (
              <Alert tone="error">{errorMessage(preview.error)}</Alert>
            ) : preview.data ? (
              <div className="space-y-3">
                {preview.data.format !== "tabular" && def.chart?.type && def.chart.type !== "table" && (
                  <Chart result={preview.data} type={def.chart.type} title={name || "Preview"} />
                )}
                <ResultTable result={preview.data} max={50} />
              </div>
            ) : (
              <Spinner label="Running" />
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

function ColumnPicker({
  label,
  options,
  value,
  onChange,
  max,
}: {
  label: string;
  options: { key: string; label: string; group?: string }[];
  value: string[];
  onChange: (v: string[]) => void;
  max?: number;
}) {
  const available = options.filter((o) => !value.includes(o.key));
  return (
    <fieldset>
      <legend className="text-sm font-medium text-slate-700">{label}</legend>
      <ul className="mt-1 space-y-1">
        {value.map((k) => (
          <li key={k} className="flex items-center justify-between rounded border border-slate-200 px-2 py-1">
            <span className="truncate">{options.find((o) => o.key === k)?.label ?? k}</span>
            <button
              type="button"
              aria-label={`Remove ${k}`}
              className="rounded p-0.5 hover:bg-slate-100"
              onClick={() => onChange(value.filter((x) => x !== k))}
            >
              <CloseIcon size={12} />
            </button>
          </li>
        ))}
      </ul>
      {(max === undefined || value.length < max) && (
        <select
          aria-label={`Add to ${label}`}
          className={controlClass(false, "mt-1")}
          value=""
          onChange={(e) => e.target.value && onChange([...value, e.target.value])}
        >
          <option value="">+ Add…</option>
          {available.map((o) => (
            <option key={o.key} value={o.key}>
              {o.label}
            </option>
          ))}
        </select>
      )}
    </fieldset>
  );
}

export function NewReportPage() {
  return <ReportBuilder />;
}

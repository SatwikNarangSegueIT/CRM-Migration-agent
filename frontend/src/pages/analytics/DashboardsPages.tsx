import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { analyticsApi, type ChartType, type Dashboard, type DashboardComponent } from "../../api/analytics";
import { ApiError, errorMessage } from "../../api/client";
import { useAuth } from "../../auth/context";
import { Chart } from "../../components/charts/Chart";
import { controlClass } from "../../components/record/FieldInput";
import { CloseIcon, GaugeIcon, PlusIcon, RefreshIcon } from "../../components/icons";
import {
  Alert,
  Button,
  EmptyState,
  FormField,
  Input,
  PageHeader,
  Spinner,
  useToast,
} from "../../components/ui";
import { cx } from "../../components/ui/cx";
import { Modal } from "../../components/ui/Modal";
import { formatDateTimeValue } from "../../lib/records";
import { NotFoundPage } from "../NotFoundPage";

export function DashboardsPage() {
  const { object } = useAuth();
  const [creating, setCreating] = useState(false);
  const dashboards = useQuery({
    queryKey: ["dashboards"],
    queryFn: ({ signal }) => analyticsApi.dashboards(signal),
  });
  return (
    <div>
      <PageHeader
        title="Dashboards"
        icon={<GaugeIcon size={22} className="text-brand-700" />}
        actions={
          object("dashboard").create && (
            <Button onClick={() => setCreating(true)}>
              <PlusIcon size={16} /> New Dashboard
            </Button>
          )
        }
      />
      {dashboards.isPending ? (
        <Spinner label="Loading" />
      ) : dashboards.isError ? (
        <Alert tone="error">{errorMessage(dashboards.error)}</Alert>
      ) : dashboards.data.length === 0 ? (
        <EmptyState
          title="No dashboards"
          description="Combine report charts into a dashboard."
          icon={<GaugeIcon size={36} />}
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {dashboards.data.map((d) => (
            <Link
              key={d.id}
              to={`/dashboards/${d.id}`}
              className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm hover:border-brand-300"
            >
              <p className="font-semibold text-brand-700">{d.name}</p>
              <p className="mt-1 text-sm text-slate-600">{d.description}</p>
              <p className="mt-2 text-xs text-slate-500">
                {d.components.length} components · {d.folder_name}
              </p>
            </Link>
          ))}
        </div>
      )}
      {creating && <DashboardEditor dashboard={null} onClose={() => setCreating(false)} />}
    </div>
  );
}

export function DashboardPage() {
  const { id = "" } = useParams();
  const [editing, setEditing] = useState(false);
  const run = useQuery({
    queryKey: ["dashboard-run", id],
    queryFn: ({ signal }) => analyticsApi.runDashboard(id, signal),
  });
  if (run.isPending) return <Spinner label="Loading dashboard" />;
  if (run.isError)
    return run.error instanceof ApiError && run.error.status === 404 ? (
      <NotFoundPage />
    ) : (
      <Alert tone="error">{errorMessage(run.error)}</Alert>
    );
  const d = run.data;
  return (
    <div className="space-y-3">
      <PageHeader
        title={d.dashboard.name}
        subtitle={`${d.viewing_as ? `Viewing as ${d.viewing_as} · ` : ""}As of ${formatDateTimeValue(d.run_at)}`}
        breadcrumbs={[{ label: "Dashboards", to: "/dashboards" }, { label: d.dashboard.name }]}
        icon={<GaugeIcon size={22} className="text-brand-700" />}
        actions={
          <>
            <Button variant="secondary" onClick={() => void run.refetch()} loading={run.isFetching}>
              <RefreshIcon size={16} /> Refresh
            </Button>
            {d.dashboard.can_edit && <Button onClick={() => setEditing(true)}>Edit</Button>}
          </>
        }
      />
      <div className="grid gap-3 md:grid-cols-3">
        {d.components.map((c, i) => (
          <section
            key={i}
            aria-label={c.title}
            className={cx(
              "rounded-lg border border-slate-200 bg-white shadow-sm",
              c.width === 3 ? "md:col-span-3" : c.width === 2 ? "md:col-span-2" : "",
            )}
          >
            <header className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5">
              <h2 className="text-sm font-semibold text-slate-900">{c.title || c.result?.report.name}</h2>
              <Link to={`/reports/${c.report_id}`} className="text-xs text-brand-700 hover:underline">
                View report
              </Link>
            </header>
            <div className="p-4">
              {c.error ? (
                <p className="text-sm text-red-700">{c.error}</p>
              ) : c.result ? (
                <Chart result={c.result} type={c.chart} title={c.title} />
              ) : null}
            </div>
          </section>
        ))}
      </div>
      {editing && <DashboardEditor dashboard={d.dashboard} onClose={() => setEditing(false)} />}
    </div>
  );
}

function DashboardEditor({ dashboard, onClose }: { dashboard: Dashboard | null; onClose: () => void }) {
  const toast = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const reports = useQuery({
    queryKey: ["reports", ""],
    queryFn: ({ signal }) => analyticsApi.reports(undefined, signal),
  });
  const folders = useQuery({
    queryKey: ["report-folders"],
    queryFn: ({ signal }) => analyticsApi.folders(signal),
  });
  const [name, setName] = useState(dashboard?.name ?? "");
  const [folderId, setFolderId] = useState(dashboard?.folder_id ?? "");
  const [components, setComponents] = useState<DashboardComponent[]>(dashboard?.components ?? []);
  const save = useMutation({
    mutationFn: () =>
      analyticsApi.saveDashboard(dashboard?.id ?? null, {
        name,
        folder_id: folderId || null,
        components,
        description: dashboard?.description ?? null,
      }),
    onSuccess: (d) => {
      toast.show("Dashboard saved.");
      void queryClient.invalidateQueries({ queryKey: ["dashboards"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard-run", d.id] });
      onClose();
      navigate(`/dashboards/${d.id}`);
    },
  });
  const update = (i: number, patch: Partial<DashboardComponent>) =>
    setComponents((cs) => cs.map((c, j) => (j === i ? { ...c, ...patch } : c)));
  return (
    <Modal
      open
      onClose={onClose}
      title={dashboard ? `Edit ${dashboard.name}` : "New dashboard"}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => save.mutate()} loading={save.isPending} disabled={!name.trim()}>
            Save
          </Button>
        </>
      }
    >
      <div className="space-y-4 text-sm">
        {save.isError && <Alert tone="error">{errorMessage(save.error)}</Alert>}
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Name" required>
            {({ id }) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} />}
          </FormField>
          <FormField label="Folder">
            {({ id }) => (
              <select
                id={id}
                className={controlClass(false)}
                value={folderId}
                onChange={(e) => setFolderId(e.target.value)}
              >
                <option value="">Private</option>
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
        </div>
        <ol className="space-y-2">
          {components.map((c, i) => (
            <li
              key={i}
              className="grid gap-2 rounded border border-slate-200 p-2 sm:grid-cols-[1fr_1fr_8rem_6rem_auto]"
            >
              <select
                aria-label="Report"
                className={controlClass(false)}
                value={c.report_id}
                onChange={(e) => update(i, { report_id: e.target.value })}
              >
                {(reports.data ?? []).map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
              <Input
                aria-label="Title"
                placeholder="Title"
                value={c.title}
                onChange={(e) => update(i, { title: e.target.value })}
              />
              <select
                aria-label="Chart"
                className={controlClass(false)}
                value={c.chart}
                onChange={(e) => update(i, { chart: e.target.value as ChartType })}
              >
                {["column", "bar", "line", "donut", "funnel", "kpi", "table"].map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              <select
                aria-label="Width"
                className={controlClass(false)}
                value={c.width}
                onChange={(e) => update(i, { width: Number(e.target.value) as 1 })}
              >
                <option value={1}>Narrow</option>
                <option value={2}>Wide</option>
                <option value={3}>Full</option>
              </select>
              <button
                type="button"
                aria-label="Remove component"
                className="rounded p-2 hover:bg-slate-100"
                onClick={() => setComponents((cs) => cs.filter((_, j) => j !== i))}
              >
                <CloseIcon size={14} />
              </button>
            </li>
          ))}
        </ol>
        <Button
          size="sm"
          variant="secondary"
          disabled={!reports.data?.length}
          onClick={() =>
            setComponents((cs) => [
              ...cs,
              { report_id: reports.data![0]!.id, title: "", chart: "column", width: 1 },
            ])
          }
        >
          <PlusIcon size={14} /> Add component
        </Button>
      </div>
    </Modal>
  );
}

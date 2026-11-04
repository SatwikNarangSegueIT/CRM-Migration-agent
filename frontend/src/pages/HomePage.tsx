import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { analyticsApi } from "../api/analytics";
import { errorMessage } from "../api/client";
import { recordsApi, workspaceApi, type QueryBody } from "../api/records";
import type { FilterNode } from "../api/types";
import { useAuth } from "../auth/context";
import { Chart } from "../components/charts/Chart";
import { FieldDisplay } from "../components/record/FieldDisplay";
import { ObjectIcon } from "../components/record/ObjectIcon";
import { CheckCircleIcon, ClockIcon } from "../components/icons";
import { Spinner } from "../components/ui";
import { cx } from "../components/ui/cx";
import { formatDate, recordPath, today, useApps, useObjectMeta } from "../lib/records";
import { FirstRunGuide } from "../components/home/FirstRunGuide";

function greeting(): string {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

function Card({
  title,
  icon,
  action,
  children,
  className,
}: {
  title: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      aria-label={title}
      className={cx("flex flex-col rounded-lg border border-slate-200 bg-white shadow-sm", className)}
    >
      <header className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
          {icon}
          {title}
        </h2>
        {action}
      </header>
      <div className="flex-1">{children}</div>
    </section>
  );
}

/** "My Leads", "My Open Cases" ... a few records of one object with two detail columns. */
function RecordsCard({
  object,
  title,
  body,
  columns,
}: {
  object: string;
  title: string;
  body: QueryBody;
  columns: string[];
}) {
  const { object: access } = useAuth();
  const meta = useObjectMeta(access(object).read ? object : undefined);
  const rows = useQuery({
    queryKey: ["records", object, "home", title],
    queryFn: ({ signal }) => recordsApi.query(object, { limit: 5, ...body }, signal),
    enabled: access(object).read,
  });
  if (!access(object).read) return null;
  return (
    <Card
      title={title}
      icon={meta.data && <ObjectIcon icon={meta.data.icon} color={meta.data.color} size={22} />}
      action={
        <Link to={`/o/${object}`} className="text-xs text-brand-700 hover:underline">
          View all
        </Link>
      }
    >
      {rows.isPending ? (
        <div className="p-4">
          <Spinner label="Loading" />
        </div>
      ) : rows.isError ? (
        <p className="p-4 text-sm text-red-700">{errorMessage(rows.error)}</p>
      ) : rows.data.items.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-slate-500">Nothing here yet.</p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {rows.data.items.map((r) => (
            <li key={r.id} className="px-4 py-2 text-sm">
              <Link to={recordPath(object, r.id)} className="font-medium text-brand-700 hover:underline">
                {r.name}
              </Link>
              <p className="flex flex-wrap gap-x-3 text-xs text-slate-600">
                {columns.map((c) => (
                  <span key={c}>
                    <FieldDisplay field={meta.data?.fields[c]} record={r} apiName={c} />
                  </span>
                ))}
              </p>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function TasksCard() {
  const { object } = useAuth();
  const tasks = useQuery({
    queryKey: ["records", "task", "home-tasks"],
    queryFn: ({ signal }) =>
      recordsApi.query(
        "task",
        {
          scope: "mine",
          limit: 8,
          sort: [{ field: "due_date", direction: "asc" }],
          filters: { logic: "and", conditions: [{ field: "status", op: "not_equals", value: "Completed" }] },
        },
        signal,
      ),
    enabled: object("task").read,
  });
  if (!object("task").read) return null;
  const now = today();
  return (
    <Card
      title="My Tasks"
      icon={<CheckCircleIcon size={18} className="text-emerald-600" />}
      action={
        <Link to="/o/task" className="text-xs text-brand-700 hover:underline">
          View all
        </Link>
      }
    >
      {tasks.isPending ? (
        <div className="p-4">
          <Spinner label="Loading" />
        </div>
      ) : !tasks.data || tasks.data.items.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-slate-500">Nothing due. Nice work!</p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {tasks.data.items.map((t) => {
            const due = t.fields.due_date as string | undefined;
            const overdue = due !== undefined && due < now;
            return (
              <li key={t.id} className="flex items-center justify-between gap-2 px-4 py-2 text-sm">
                <span className="min-w-0">
                  <Link to={recordPath("task", t.id)} className="font-medium text-brand-700 hover:underline">
                    {t.name}
                  </Link>
                  {t.display.related_to && (
                    <span className="block truncate text-xs text-slate-500">{t.display.related_to.name}</span>
                  )}
                </span>
                <span
                  className={cx(
                    "flex-none text-xs",
                    overdue ? "font-semibold text-red-700" : "text-slate-500",
                  )}
                >
                  {due ? formatDate(due) : ""}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

function RecentCard() {
  const recent = useQuery({
    queryKey: ["recent", "home"],
    queryFn: ({ signal }) => workspaceApi.recent(signal, 8),
  });
  return (
    <Card title="Recent Records" icon={<ClockIcon size={18} className="text-slate-500" />}>
      {recent.isPending ? (
        <div className="p-4">
          <Spinner label="Loading" />
        </div>
      ) : !recent.data || recent.data.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-slate-500">Records you open appear here.</p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {recent.data.map((r) => (
            <li key={r.id} className="flex items-center gap-2 px-4 py-2 text-sm">
              <ObjectIcon icon={r.icon} color={r.color} size={22} />
              <Link to={recordPath(r.object, r.id)} className="truncate text-brand-700 hover:underline">
                {r.name}
              </Link>
              <span className="ml-auto flex-none text-xs text-slate-500">{r.object_label}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function DashboardCharts({ dashboardKey, max = 2 }: { dashboardKey: string; max?: number }) {
  const { object } = useAuth();
  const dashboards = useQuery({
    queryKey: ["dashboards"],
    queryFn: ({ signal }) => analyticsApi.dashboards(signal),
    enabled: object("dashboard").read,
    staleTime: 60_000,
  });
  const dash = dashboards.data?.find((d) => d.key === dashboardKey);
  const run = useQuery({
    queryKey: ["dashboard-run", dash?.id],
    queryFn: ({ signal }) => analyticsApi.runDashboard(dash!.id, signal),
    enabled: Boolean(dash),
    staleTime: 60_000,
  });
  if (!dash) return null;
  return (
    <>
      {(run.data?.components ?? [])
        .filter((c) => c.result)
        .slice(0, max)
        .map((c) => (
          <Card
            key={c.report_id + c.title}
            title={c.title}
            action={
              <Link to={`/dashboards/${dash.id}`} className="text-xs text-brand-700 hover:underline">
                Open dashboard
              </Link>
            }
          >
            <div className="p-4">
              <Chart result={c.result!} type={c.chart} title={c.title} />
            </div>
          </Card>
        ))}
    </>
  );
}

const OPEN: FilterNode = { logic: "and", conditions: [{ field: "is_closed", op: "equals", value: false }] };

function MarketingChecklist() {
  const { object } = useAuth();
  const counts = useQuery({
    queryKey: ["marketing-checklist"],
    queryFn: async ({ signal }) => {
      const out: Record<string, number> = {};
      for (const o of ["consent", "segment", "email_template", "campaign", "email_send"]) {
        out[o] = object(o).read ? (await recordsApi.query(o, { limit: 1 }, signal)).total : 0;
      }
      return out;
    },
  });
  const steps = [
    { key: "consent", label: "Capture e-mail consent", to: "/o/consent" },
    { key: "segment", label: "Build a segment", to: "/o/segment" },
    { key: "email_template", label: "Design an e-mail template", to: "/o/email_template" },
    { key: "campaign", label: "Plan a campaign", to: "/o/campaign" },
    { key: "email_send", label: "Send your first e-mail", to: "/o/email_send" },
  ];
  return (
    <Card title="Marketing setup checklist">
      <ol className="space-y-2 p-4 text-sm">
        {steps.map((s, i) => {
          const done = (counts.data?.[s.key] ?? 0) > 0;
          return (
            <li key={s.key} className="flex items-center gap-2">
              <span
                className={cx(
                  "flex h-6 w-6 flex-none items-center justify-center rounded-full text-xs font-semibold",
                  done ? "bg-emerald-600 text-white" : "bg-slate-100 text-slate-600",
                )}
              >
                {done ? "✓" : i + 1}
              </span>
              <Link
                to={s.to}
                className={cx("hover:underline", done ? "text-slate-500 line-through" : "text-brand-700")}
              >
                {s.label}
              </Link>
            </li>
          );
        })}
      </ol>
    </Card>
  );
}

const STARTERS: Record<string, { title: string; text: string; to: string; object?: string }[]> = {
  sales: [
    { title: "Add a lead", text: "Capture a new enquiry and qualify it.", to: "/o/lead", object: "lead" },
    {
      title: "Track an opportunity",
      text: "Move deals through the pipeline.",
      to: "/o/opportunity",
      object: "opportunity",
    },
    {
      title: "Send a quote",
      text: "Price products and convert to an invoice.",
      to: "/o/quote",
      object: "quote",
    },
  ],
  service: [
    {
      title: "Work the queue",
      text: "Accept cases waiting in your queues.",
      to: "/o/case?scope=queue",
      object: "case",
    },
    { title: "Log a case", text: "Record a customer request with its SLA.", to: "/o/case", object: "case" },
  ],
  billing: [
    {
      title: "Add a product",
      text: "Products carry a standard price and tax rate.",
      to: "/o/product",
      object: "product",
    },
    {
      title: "Raise an invoice",
      text: "Issue tax invoices and record payments.",
      to: "/o/invoice",
      object: "invoice",
    },
  ],
  marketing: [
    {
      title: "Plan a campaign",
      text: "Group activity, members and results.",
      to: "/o/campaign",
      object: "campaign",
    },
    {
      title: "Send an e-mail",
      text: "Reach a segment with consent built in.",
      to: "/o/email_send",
      object: "email_send",
    },
  ],
};

export function HomePage() {
  const { appKey } = useParams();
  const { me, object } = useAuth();
  const apps = useApps();
  const app = apps.data?.find((a) => a.key === appKey);
  const key = app?.key ?? "home";
  const starters = (STARTERS[key] ?? STARTERS.sales!).filter((s) => !s.object || object(s.object).read);
  const firstName = me?.user.name.split(" ")[0] ?? "";

  return (
    <div className="space-y-4">
      <section className="rounded-lg bg-gradient-to-r from-[#032d60] to-brand-700 px-6 py-5 text-white shadow-sm">
        <p className="text-sm text-blue-100">{app ? app.label : "Home"}</p>
        <h1 className="text-2xl font-semibold">
          {greeting()}, {firstName}
        </h1>
        <p className="mt-1 text-sm text-blue-100">
          {app?.description ?? "Here's what needs your attention today."}
        </p>
        {starters.length > 0 && (
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {starters.map((s) => (
              <Link key={s.title} to={s.to} className="rounded-md bg-white/10 px-4 py-3 hover:bg-white/20">
                <p className="font-semibold">{s.title}</p>
                <p className="text-xs text-blue-100">{s.text}</p>
              </Link>
            ))}
          </div>
        )}
      </section>

      {key === "home" && me?.is_system_admin && <FirstRunGuide />}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {key === "marketing" && <MarketingChecklist />}
        {(key === "home" || key === "sales") && (
          <RecordsCard
            object="opportunity"
            title="My Open Opportunities"
            body={{ scope: "mine", filters: OPEN, sort: [{ field: "close_date", direction: "asc" }] }}
            columns={["stage", "amount", "close_date"]}
          />
        )}
        {(key === "home" || key === "sales" || key === "marketing") && (
          <RecordsCard
            object="lead"
            title="My Leads"
            body={{
              scope: "mine",
              filters: { logic: "and", conditions: [{ field: "is_converted", op: "equals", value: false }] },
              sort: [{ field: "created_at", direction: "desc" }],
            }}
            columns={["company", "status"]}
          />
        )}
        {(key === "home" || key === "service") && (
          <RecordsCard
            object="case"
            title="My Open Cases"
            body={{
              scope: "mine",
              filters: { logic: "and", conditions: [{ field: "status", op: "not_equals", value: "Closed" }] },
              sort: [{ field: "created_at", direction: "desc" }],
            }}
            columns={["subject", "status", "priority"]}
          />
        )}
        {key === "service" && (
          <RecordsCard
            object="case"
            title="Queue: waiting to be accepted"
            body={{
              scope: "queue",
              filters: { logic: "and", conditions: [{ field: "status", op: "not_equals", value: "Closed" }] },
              sort: [{ field: "created_at", direction: "asc" }],
            }}
            columns={["subject", "priority"]}
          />
        )}
        {key === "billing" && (
          <RecordsCard
            object="invoice"
            title="Overdue Invoices"
            body={{
              filters: {
                logic: "and",
                conditions: [
                  { field: "status", op: "in", value: ["Issued", "Partially Paid"] },
                  { field: "due_date", op: "lt", value: "TODAY" },
                ],
              },
              sort: [{ field: "due_date", direction: "asc" }],
            }}
            columns={["account", "balance", "due_date"]}
          />
        )}
        {key === "marketing" && (
          <RecordsCard
            object="email_send"
            title="E-mail history"
            body={{ sort: [{ field: "created_at", direction: "desc" }] }}
            columns={["status", "sent_at", "opened_count"]}
          />
        )}
        {key === "migration_practice" && (
          <RecordsCard
            object="matter"
            title="My Active Matters"
            body={{
              scope: "mine",
              filters: { logic: "and", conditions: [{ field: "status", op: "equals", value: "Active" }] },
              sort: [{ field: "created_at", direction: "desc" }],
            }}
            columns={["client", "stage", "visa_type"]}
          />
        )}
        <TasksCard />
        <RecentCard />
        {(key === "home" || key === "sales") && <DashboardCharts dashboardKey="sales_dashboard" />}
        {key === "service" && <DashboardCharts dashboardKey="service_dashboard" />}
        {key === "billing" && <DashboardCharts dashboardKey="billing_dashboard" />}
        {key === "marketing" && <DashboardCharts dashboardKey="marketing_dashboard" max={1} />}
        {key === "migration_practice" && <DashboardCharts dashboardKey="ma_practice_dashboard" />}
      </div>
    </div>
  );
}

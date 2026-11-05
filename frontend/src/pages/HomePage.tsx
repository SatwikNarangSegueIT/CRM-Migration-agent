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
      className={cx("flex flex-col rounded-xl border border-slate-200/80 bg-white shadow-card", className)}
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
  titleFields,
}: {
  object: string;
  title: string;
  body: QueryBody;
  columns: string[];
  /** Fields that name the record better than its number (a deadline is "BAS Q1 Jul-Sep"). */
  titleFields?: string[];
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
                {(titleFields ?? [])
                  .map((f) => r.fields[f])
                  .filter(Boolean)
                  .join(" ") || r.name}
              </Link>
              <p className="flex flex-wrap gap-x-3 text-xs text-slate-600">
                {columns
                  .filter((c) => {
                    if (c === "created_at" || c === "updated_at") return true;
                    const v = r.fields[c];
                    return v !== null && v !== undefined && v !== "";
                  })
                  .map((c) => (
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
  // By key, in one call: listing the dashboards first to find the id cost a second round trip.
  const run = useQuery({
    queryKey: ["dashboard-run-key", dashboardKey],
    queryFn: ({ signal }) => analyticsApi.runDashboardByKey(dashboardKey, signal),
    enabled: object("dashboard").read,
    staleTime: 60_000,
    retry: false,
  });
  const dash = run.data?.dashboard;
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
  legal_practice: [
    {
      title: "Open a matter",
      text: "Conflict check and costs disclosure come first.",
      to: "/o/legal_matter",
      object: "legal_matter",
    },
    {
      title: "Record time",
      text: "6-minute units, billed straight to an invoice.",
      to: "/o/legal_time_entry",
      object: "legal_time_entry",
    },
    {
      title: "Trust ledger",
      text: "Receipts, payments and transfers to office.",
      to: "/o/trust_transaction",
      object: "trust_transaction",
    },
  ],
  migration_practice: [
    {
      title: "Open a matter",
      text: "Visa matters from consultation to decision.",
      to: "/o/matter",
      object: "matter",
    },
    {
      title: "Add a client",
      text: "Client details, passport and visa expiry.",
      to: "/o/contact",
      object: "contact",
    },
  ],
  accounting_practice: [
    {
      title: "Start an engagement",
      text: "Engagement letter, documents, review and lodgement.",
      to: "/o/engagement",
      object: "engagement",
    },
    {
      title: "Lodgement deadlines",
      text: "What is due and overdue for your clients.",
      to: "/o/lodgement_deadline",
      object: "lodgement_deadline",
    },
    {
      title: "Record time",
      text: "Track WIP and recoverability.",
      to: "/o/engagement_time_entry",
      object: "engagement_time_entry",
    },
  ],
  loan_broking: [
    {
      title: "New loan application",
      text: "Fact find, credit guide and BID before lodging.",
      to: "/o/loan_application",
      object: "loan_application",
    },
    { title: "Lender panel", text: "Lenders, BDMs and commission rates.", to: "/o/lender", object: "lender" },
    {
      title: "Commissions",
      text: "Upfront, trail and clawback ledger.",
      to: "/o/commission",
      object: "commission",
    },
  ],
};

export function HomePage() {
  const { appKey } = useParams();
  const { me, object } = useAuth();
  const apps = useApps();
  // The workspace's own app (law firm, accounting practice...) is the home page when one is set.
  const app = appKey ? apps.data?.find((a) => a.key === appKey) : apps.data?.find((a) => a.is_primary);
  const key = app?.key ?? "home";
  const isHome = !appKey;
  const starters = (STARTERS[key] ?? STARTERS.sales!).filter((s) => !s.object || object(s.object).read);
  const firstName = me?.user.name.split(" ")[0] ?? "";

  // Until the apps are known the layout isn't: rendering the generic cards first would fire queries for
  // objects this workspace doesn't use (and flash the wrong page).
  if (apps.isPending) {
    return (
      <div className="space-y-4" aria-busy="true">
        <div className="h-36 animate-pulse rounded-xl bg-slate-200/70" />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-48 animate-pulse rounded-xl bg-slate-200/50" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <section className="surface-brand rounded-2xl px-6 py-7 text-white shadow-pop sm:px-8">
        <p className="text-xs font-medium uppercase tracking-wider text-white/70">
          {app ? app.label : "Home"}
        </p>
        <h1 className="mt-1 text-[26px] font-semibold tracking-tight">
          {greeting()}, {firstName}
        </h1>
        <p className="mt-1 text-sm text-white/75">
          {app?.description ?? "Here's what needs your attention today."}
        </p>
        {starters.length > 0 && (
          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {starters.map((s) => (
              <Link
                key={s.title}
                to={s.to}
                className="group rounded-xl bg-white/[0.08] px-4 py-3.5 ring-1 ring-inset ring-white/15 backdrop-blur-sm transition hover:-translate-y-0.5 hover:bg-white/[0.14] hover:ring-white/25"
              >
                <p className="flex items-center justify-between font-medium">
                  {s.title}
                  <span
                    aria-hidden="true"
                    className="text-white/50 transition group-hover:translate-x-0.5 group-hover:text-white"
                  >
                    →
                  </span>
                </p>
                <p className="mt-0.5 text-xs text-white/70">{s.text}</p>
              </Link>
            ))}
          </div>
        )}
      </section>

      {isHome && me?.is_system_admin && <FirstRunGuide />}

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
        {key === "legal_practice" && (
          <RecordsCard
            object="legal_matter"
            title="My Open Matters"
            body={{
              scope: "mine",
              filters: { logic: "and", conditions: [{ field: "status", op: "not_equals", value: "Closed" }] },
              sort: [{ field: "created_at", direction: "desc" }],
            }}
            columns={["title", "stage", "limitation_date"]}
          />
        )}
        {key === "accounting_practice" && (
          <RecordsCard
            object="lodgement_deadline"
            title="Lodgements Due"
            body={{
              filters: {
                logic: "and",
                conditions: [{ field: "status", op: "in", value: ["Upcoming", "Overdue"] }],
              },
              sort: [{ field: "due_date", direction: "asc" }],
            }}
            titleFields={["lodgement_type", "period"]}
            columns={["client", "due_date", "status"]}
          />
        )}
        {key === "accounting_practice" && (
          <RecordsCard
            object="engagement"
            title="My Engagements"
            body={{
              scope: "mine",
              filters: {
                logic: "and",
                conditions: [{ field: "stage", op: "not_equals", value: "Complete" }],
              },
              sort: [{ field: "due_date", direction: "asc" }],
            }}
            columns={["client", "stage", "due_date"]}
          />
        )}
        {key === "loan_broking" && (
          <RecordsCard
            object="loan_application"
            title="My Pipeline"
            body={{
              scope: "mine",
              filters: {
                logic: "and",
                conditions: [{ field: "stage", op: "not_in", value: ["Settled", "Declined"] }],
              },
              sort: [{ field: "created_at", direction: "desc" }],
            }}
            columns={["primary_borrower", "loan_amount", "stage"]}
          />
        )}
        <TasksCard />
        <RecentCard />
        {(key === "home" || key === "sales") && <DashboardCharts dashboardKey="sales_dashboard" />}
        {key === "service" && <DashboardCharts dashboardKey="service_dashboard" />}
        {key === "billing" && <DashboardCharts dashboardKey="billing_dashboard" />}
        {key === "marketing" && <DashboardCharts dashboardKey="marketing_dashboard" max={1} />}
        {key === "migration_practice" && <DashboardCharts dashboardKey="ma_practice_dashboard" />}
        {key === "legal_practice" && <DashboardCharts dashboardKey="lp_practice_dashboard" />}
        {key === "accounting_practice" && <DashboardCharts dashboardKey="ap_practice_dashboard" />}
        {key === "loan_broking" && <DashboardCharts dashboardKey="lb_broker_dashboard" />}
      </div>
    </div>
  );
}

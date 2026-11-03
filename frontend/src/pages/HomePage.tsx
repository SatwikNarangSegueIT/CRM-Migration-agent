import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import { getLive, getReady, type CheckStatus } from "../api/health";
import { useAuth } from "../auth/context";
import {
  ClipboardIcon,
  ClockIcon,
  PulseIcon,
  SettingsIcon,
  ShieldIcon,
  TasksIcon,
  UsersIcon,
} from "../components/icons";
import { EmptyState } from "../components/ui";

function StatusBadge({ status }: { status: CheckStatus }) {
  const ok = status === "ok";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${
        ok ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-800"
      }`}
    >
      {ok ? "Operational" : "Unavailable"}
    </span>
  );
}

function HomeCard({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
  return (
    <section
      className="rounded-xl border border-slate-200 bg-white shadow-sm"
      aria-labelledby={`card-${title}`}
    >
      <header className="flex items-center gap-2 px-5 pt-4">
        <span
          aria-hidden="true"
          className="flex h-7 w-7 items-center justify-center rounded-md bg-brand-50 text-brand-700"
        >
          {icon}
        </span>
        <h2 id={`card-${title}`} className="text-base font-semibold text-slate-900">
          {title}
        </h2>
      </header>
      <div className="px-5 pb-5 pt-2">{children}</div>
    </section>
  );
}

function SystemStatus() {
  const live = useQuery({ queryKey: ["health", "live"], queryFn: ({ signal }) => getLive(signal) });
  const ready = useQuery({ queryKey: ["health", "ready"], queryFn: ({ signal }) => getReady(signal) });

  return (
    <HomeCard title="System status" icon={<PulseIcon size={16} />}>
      {live.isPending || ready.isPending ? (
        <p className="text-sm text-slate-500">Checking services…</p>
      ) : live.isError ? (
        <p role="alert" className="text-sm text-red-700">
          {live.error instanceof ApiError ? live.error.message : "Could not load status."}
        </p>
      ) : (
        <dl className="divide-y divide-slate-100 text-sm">
          <div className="flex items-center justify-between py-2">
            <dt>API ({live.data.environment})</dt>
            <dd>
              <StatusBadge status="ok" />
            </dd>
          </div>
          {ready.isError ? (
            <div className="flex items-center justify-between py-2">
              <dt>Dependencies</dt>
              <dd>
                <StatusBadge status="error" />
              </dd>
            </div>
          ) : (
            Object.entries(ready.data.checks).map(([name, status]) => (
              <div key={name} className="flex items-center justify-between py-2">
                <dt className="capitalize">{name}</dt>
                <dd>
                  <StatusBadge status={status} />
                </dd>
              </div>
            ))
          )}
        </dl>
      )}
    </HomeCard>
  );
}

type Suggestion = { to: string; label: string; description: string; icon: ReactNode; permission?: string };

const SUGGESTIONS: Suggestion[] = [
  {
    to: "/admin/users",
    label: "Manage users",
    description: "Invite staff, change roles, reset MFA.",
    icon: <UsersIcon size={18} />,
    permission: "user.manage",
  },
  {
    to: "/admin/audit",
    label: "Audit log",
    description: "Review every sign-in and change.",
    icon: <ClipboardIcon size={18} />,
    permission: "audit.read",
  },
  {
    to: "/account",
    label: "Account settings",
    description: "Password and two-step verification.",
    icon: <SettingsIcon size={18} />,
  },
];

export function HomePage() {
  const { me, can } = useAuth();
  const suggestions = SUGGESTIONS.filter((l) => !l.permission || can(l.permission));
  const firstName = me?.user.name.split(/\s+/)[0] ?? "";

  return (
    <div className="space-y-4">
      <section className="rounded-xl bg-gradient-to-r from-indigo-100 via-violet-50 to-sky-100 px-6 py-6 shadow-sm">
        <h1 className="text-2xl font-semibold text-slate-900">Welcome, {firstName}</h1>
        <p className="mt-1 text-sm text-slate-700">
          Signed in as <span className="font-medium">{me?.user.role_label}</span>. Here are a few places to
          start.
        </p>
        <ul className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {suggestions.map((s) => (
            <li key={s.to}>
              <Link
                to={s.to}
                className="flex h-full items-start gap-3 rounded-lg border border-white/70 bg-white/80 p-4 shadow-sm backdrop-blur hover:border-brand-300 hover:bg-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-700"
              >
                <span
                  aria-hidden="true"
                  className="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-brand-700 text-white"
                >
                  {s.icon}
                </span>
                <span>
                  <span className="block font-medium text-slate-900">{s.label}</span>
                  <span className="mt-0.5 block text-sm text-slate-600">{s.description}</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <div className="grid gap-4 lg:grid-cols-3">
        <HomeCard title="My Tasks" icon={<TasksIcon size={16} />}>
          <EmptyState
            icon={<TasksIcon size={32} />}
            title="Nothing due"
            description="Tasks and deadlines for your matters will appear here."
          />
        </HomeCard>
        <HomeCard title="Recent Records" icon={<ClockIcon size={16} />}>
          <EmptyState
            icon={<ShieldIcon size={32} />}
            title="No recent records"
            description="Leads, contacts and matters you open will be listed here."
          />
        </HomeCard>
        <SystemStatus />
      </div>
    </div>
  );
}

import { useQuery } from "@tanstack/react-query";
import { getLive, getReady, type CheckStatus } from "../api/health";
import { ApiError } from "../api/client";

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

export function HomePage() {
  const live = useQuery({ queryKey: ["health", "live"], queryFn: ({ signal }) => getLive(signal) });
  const ready = useQuery({ queryKey: ["health", "ready"], queryFn: ({ signal }) => getReady(signal) });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Welcome to MigrateCRM</h1>
        <p className="mt-1 text-sm text-slate-600">
          Foundations are in place. CRM modules arrive in the next phases.
        </p>
      </div>

      <section aria-labelledby="status-heading" className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 id="status-heading" className="text-base font-semibold">
          System status
        </h2>
        {live.isPending || ready.isPending ? (
          <p className="mt-3 text-sm text-slate-500">Checking services…</p>
        ) : live.isError ? (
          <p role="alert" className="mt-3 text-sm text-red-700">
            {live.error instanceof ApiError ? live.error.message : "Could not load status."}
          </p>
        ) : (
          <dl className="mt-3 divide-y divide-slate-100 text-sm">
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
      </section>
    </div>
  );
}

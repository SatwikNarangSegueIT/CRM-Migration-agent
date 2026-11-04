import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { signupApi } from "../../api/signup";

/** Getting-started checklist for a new workspace's administrators (hidden once done or dismissed). */
export function FirstRunGuide() {
  const queryClient = useQueryClient();
  const guide = useQuery({
    queryKey: ["onboarding"],
    queryFn: ({ signal }) => signupApi.onboarding(signal),
    staleTime: 60_000,
  });
  const dismiss = useMutation({
    mutationFn: signupApi.dismissOnboarding,
    onSuccess: (data) => queryClient.setQueryData(["onboarding"], data),
  });
  if (!guide.data?.visible) return null;
  const steps = guide.data.steps;
  const done = steps.filter((s) => s.done).length;

  return (
    <section
      aria-labelledby="first-run-title"
      className="rounded-lg border border-brand-200 bg-white p-5 shadow-sm"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 id="first-run-title" className="text-base font-semibold text-slate-900">
            Get your workspace ready
          </h2>
          <p className="text-sm text-slate-600">
            {done} of {steps.length} done
          </p>
        </div>
        <button
          type="button"
          onClick={() => dismiss.mutate()}
          className="text-sm font-medium text-slate-500 hover:text-slate-800"
        >
          Dismiss
        </button>
      </div>
      <div className="mt-3 h-1.5 rounded-full bg-slate-100" aria-hidden="true">
        <div
          className="h-1.5 rounded-full bg-brand-600"
          style={{ width: `${(100 * done) / steps.length}%` }}
        />
      </div>
      <ol className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {steps.map((s) => (
          <li key={s.key}>
            <Link
              to={s.href}
              className="block h-full rounded-md border border-slate-200 px-4 py-3 hover:border-brand-400 hover:bg-brand-50"
            >
              <p className="flex items-center gap-2 font-medium text-slate-900">
                <span
                  aria-hidden="true"
                  className={
                    s.done
                      ? "flex h-5 w-5 items-center justify-center rounded-full bg-green-600 text-xs text-white"
                      : "h-5 w-5 rounded-full border-2 border-slate-300"
                  }
                >
                  {s.done ? "✓" : ""}
                </span>
                {s.label}
                {s.done && <span className="sr-only">(done)</span>}
              </p>
              <p className="mt-1 text-xs text-slate-600">{s.description}</p>
            </Link>
          </li>
        ))}
      </ol>
    </section>
  );
}

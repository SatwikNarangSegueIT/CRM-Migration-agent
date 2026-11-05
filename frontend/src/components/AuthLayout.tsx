import type { ReactNode } from "react";
import { useBranding } from "../lib/branding";
import { CheckIcon } from "./icons";
import { Logo } from "./Logo";

const POINTS = [
  "Built for law firms, migration agents, accountants and brokers",
  "Compliance workflows: conflicts, trust, BID, engagement letters",
  "Client portal, documents and deadlines in one place",
];

/** A glimpse of the product on the brand panel (decorative). */
function PreviewCard() {
  const rows: [string, string, string][] = [
    ["Identity verified", "Yes", "bg-emerald-400"],
    ["Engagement letter", "Signed", "bg-sky-300"],
    ["Next deadline", "14 Nov", "bg-amber-300"],
  ];
  return (
    <div
      aria-hidden="true"
      className="mt-12 rounded-2xl border border-white/15 bg-white/10 p-5 shadow-2xl backdrop-blur-md"
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wider text-white/60">Client file</p>
          <p className="mt-0.5 font-semibold">Ava Nguyen</p>
        </div>
        <span className="rounded-full bg-white/15 px-2.5 py-1 text-[11px] font-medium">Active</span>
      </div>
      <ul className="mt-4 space-y-2.5">
        {rows.map(([label, value, dot]) => (
          <li key={label} className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-2 text-white/75">
              <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
              {label}
            </span>
            <span className="font-medium">{value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Sign-in, sign-up and recovery pages: a quiet brand panel beside a focused form (panel hidden on phones). */
export function AuthLayout({
  title,
  subtitle,
  children,
  aside,
  wide = false,
}: {
  title: string;
  subtitle?: ReactNode;
  children: ReactNode;
  /** Replaces the default brand panel content. */
  aside?: ReactNode;
  wide?: boolean;
}) {
  const brand = useBranding();
  return (
    <div className="grid min-h-screen bg-white lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <aside className="surface-brand hidden px-12 py-10 text-white lg:flex lg:flex-col">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -right-32 -top-32 h-96 w-96 rounded-full bg-brand-500/30 blur-3xl"
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -bottom-40 -left-24 h-96 w-96 rounded-full bg-brand-700/40 blur-3xl"
        />
        <div className="relative flex items-center gap-2 text-lg font-semibold">
          {brand.logoUrl && (
            <img src={brand.logoUrl} alt="" className="h-8 w-8 rounded-md bg-white/10 object-contain p-1" />
          )}
          {brand.name}
        </div>
        <div className="relative my-auto max-w-md">
          {aside ?? (
            <>
              <h2 className="text-3xl font-semibold leading-tight tracking-tight">
                The practice CRM for regulated professions.
              </h2>
              <ul className="mt-8 space-y-4">
                {POINTS.map((p) => (
                  <li key={p} className="flex gap-3 text-sm text-white/85">
                    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white/15">
                      <CheckIcon size={12} />
                    </span>
                    {p}
                  </li>
                ))}
              </ul>
              <PreviewCard />
            </>
          )}
        </div>
        <p className="relative text-xs text-white/50">
          © {new Date().getFullYear()} {brand.name}
        </p>
      </aside>

      <div className="flex min-h-screen flex-col px-4 py-8 sm:px-8">
        <Logo className="text-base lg:hidden" />
        <main className={`m-auto w-full py-8 ${wide ? "max-w-xl" : "max-w-sm"}`}>
          <h1 className="text-[28px] font-semibold tracking-tight text-slate-900">{title}</h1>
          {subtitle && <div className="mt-1.5 text-sm text-slate-600">{subtitle}</div>}
          <div className="mt-8">{children}</div>
        </main>
      </div>
    </div>
  );
}

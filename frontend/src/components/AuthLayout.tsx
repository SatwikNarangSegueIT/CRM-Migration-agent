import type { ReactNode } from "react";
import { useBranding } from "../lib/branding";
import { CheckIcon } from "./icons";
import { Logo } from "./Logo";

const POINTS = [
  "Built for law firms, migration agents, accountants and brokers",
  "Compliance workflows: conflicts, trust, BID, engagement letters",
  "Client portal, documents and deadlines in one place",
];

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
      <aside className="relative hidden overflow-hidden bg-brand-900 px-12 py-10 text-white lg:flex lg:flex-col">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -right-32 -top-32 h-96 w-96 rounded-full bg-brand-500/30 blur-3xl"
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -bottom-40 -left-24 h-96 w-96 rounded-full bg-brand-700/40 blur-3xl"
        />
        <div className="relative flex items-center gap-2 text-lg font-semibold">
          <img src={brand.logoUrl ?? "/favicon.svg"} alt="" className="h-8 w-8 rounded-md bg-white/10 p-1" />
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
            </>
          )}
        </div>
      </aside>

      <div className="flex min-h-screen flex-col px-4 py-8 sm:px-8">
        <Logo className="text-base lg:hidden" />
        <main className={`m-auto w-full py-8 ${wide ? "max-w-xl" : "max-w-sm"}`}>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
          {subtitle && <div className="mt-1.5 text-sm text-slate-600">{subtitle}</div>}
          <div className="mt-8">{children}</div>
        </main>
      </div>
    </div>
  );
}

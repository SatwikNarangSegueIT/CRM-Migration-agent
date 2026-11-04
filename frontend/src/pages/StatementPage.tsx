// Printable client money statements: a law firm's trust account statement for a matter (Uniform General
// Rules: given to the client at the end of the matter or on request) and a migration agent's client
// account statement for a client (Code of Conduct: on request). Print or save as PDF from the browser.
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { apiRequest, errorMessage } from "../api/client";
import { Alert, Button, Spinner } from "../components/ui";
import { useBranding } from "../lib/branding";
import { recordPath } from "../lib/records";

type Row = {
  id: string;
  number: string;
  date: string | null;
  type: string;
  payer_payee?: string | null;
  amount: number | string;
  signed_amount: number | string;
  reference?: string | null;
  running_balance: number | string;
};
type Statement = {
  matter?: { id: string; name: string; title?: string | null };
  client?: { id: string; name: string };
  transactions: Row[];
  balance: number | string;
};

const KINDS = {
  trust: {
    title: "Trust Account Statement",
    url: (id: string) => `/packs/legal_practice/trust-statement/${id}`,
    back: (id: string) => recordPath("legal_matter", id),
  },
  "client-account": {
    title: "Client Account Statement",
    url: (id: string) => `/packs/migration_agency/statement/${id}`,
    back: (id: string) => recordPath("contact", id),
  },
} as const;

const money = (v: number | string) =>
  Number(v).toLocaleString("en-AU", { style: "currency", currency: "AUD" });
const day = (v: string | null) =>
  v ? new Date(`${v.slice(0, 10)}T00:00:00`).toLocaleDateString("en-AU", { dateStyle: "medium" }) : "";

export function StatementPage() {
  const { kind = "", id = "" } = useParams();
  const brand = useBranding();
  const spec = KINDS[kind as keyof typeof KINDS];
  const q = useQuery({
    queryKey: ["statement", kind, id],
    queryFn: ({ signal }) => apiRequest<Statement>(spec.url(id), { signal }),
    enabled: Boolean(spec),
  });
  if (!spec) return <Alert tone="error">Unknown statement.</Alert>;
  if (q.isPending) return <Spinner label="Loading" />;
  if (q.isError) return <Alert tone="error">{errorMessage(q.error)}</Alert>;
  const s = q.data;
  const subject = s.matter
    ? `${s.matter.name}${s.matter.title ? ` · ${s.matter.title}` : ""}`
    : (s.client?.name ?? "");
  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div className="flex items-center justify-between gap-3 print:hidden">
        <Link to={spec.back(id)} className="text-sm text-brand-700 hover:underline">
          Back to the record
        </Link>
        <Button onClick={() => window.print()}>Print or save as PDF</Button>
      </div>
      <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm print:border-0 print:shadow-none">
        <header className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 pb-4">
          <div>
            <p className="text-lg font-semibold text-slate-900">{brand.name}</p>
            <h1 className="mt-1 text-2xl font-semibold text-slate-900">{spec.title}</h1>
            <p className="mt-1 text-sm text-slate-700">{subject}</p>
          </div>
          <dl className="text-right text-sm">
            <dt className="text-xs text-slate-500">As at</dt>
            <dd className="text-slate-900">
              {new Date().toLocaleDateString("en-AU", { dateStyle: "long" })}
            </dd>
            <dt className="mt-2 text-xs text-slate-500">Balance held</dt>
            <dd className="text-lg font-semibold text-slate-900">{money(s.balance)}</dd>
          </dl>
        </header>
        {s.transactions.length === 0 ? (
          <p className="py-6 text-sm text-slate-500">No transactions.</p>
        ) : (
          <table className="mt-4 w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-600">
                <th scope="col" className="py-2 pr-2 font-semibold">
                  Date
                </th>
                <th scope="col" className="py-2 pr-2 font-semibold">
                  No.
                </th>
                <th scope="col" className="py-2 pr-2 font-semibold">
                  Details
                </th>
                <th scope="col" className="py-2 pr-2 text-right font-semibold">
                  Received
                </th>
                <th scope="col" className="py-2 pr-2 text-right font-semibold">
                  Paid out
                </th>
                <th scope="col" className="py-2 text-right font-semibold">
                  Balance
                </th>
              </tr>
            </thead>
            <tbody>
              {s.transactions.map((t) => {
                const signed = Number(t.signed_amount);
                return (
                  <tr key={t.id} className="border-b border-slate-100 align-top">
                    <td className="py-2 pr-2 whitespace-nowrap">{day(t.date)}</td>
                    <td className="py-2 pr-2 whitespace-nowrap">{t.number}</td>
                    <td className="py-2 pr-2">
                      {t.type}
                      {t.payer_payee ? ` · ${t.payer_payee}` : ""}
                      {t.reference ? (
                        <span className="block text-xs text-slate-500">{t.reference}</span>
                      ) : null}
                    </td>
                    <td className="py-2 pr-2 text-right">{signed > 0 ? money(signed) : ""}</td>
                    <td className="py-2 pr-2 text-right">{signed < 0 ? money(-signed) : ""}</td>
                    <td className="py-2 text-right">{money(t.running_balance)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
        <p className="mt-6 text-xs text-slate-500">
          Money held on your behalf is kept in a separate account and paid out only as you authorised or to
          pay invoices issued to you. Please tell us promptly if anything on this statement is not as you
          expect.
        </p>
      </section>
    </div>
  );
}

import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { errorMessage, fieldError } from "../../api/client";
import { signupApi, type DomainKey } from "../../api/signup";
import { AuthLayout } from "../../components/AuthLayout";
import { NewPasswordFields } from "../../components/NewPasswordFields";
import { Alert, Button, Checkbox, Spinner, TextField } from "../../components/ui";
import { cx } from "../../components/ui/cx";
import { passwordsReady } from "../../lib/password";

const DOMAIN_ICONS: Record<DomainKey, string> = {
  legal: "⚖️",
  migration: "🛂",
  accounting: "📊",
  lending: "🏠",
};

/** Public sign-up: choose the kind of firm, then the firm and administrator details. */
export function SignupPage() {
  const domains = useQuery({
    queryKey: ["signup", "domains"],
    queryFn: ({ signal }) => signupApi.domains(signal),
  });
  const [domain, setDomain] = useState<DomainKey | null>(null);
  const [step, setStep] = useState<"domain" | "details">("domain");
  const [firm, setFirm] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [abn, setAbn] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [terms, setTerms] = useState(false);
  const [honeypot, setHoneypot] = useState("");

  const submit = useMutation({
    mutationFn: () =>
      signupApi.start({
        domain: domain!,
        firm_name: firm,
        name,
        email,
        password,
        abn: abn || null,
        accept_terms: terms,
        website_url: honeypot || null,
      }),
  });
  const chosen = domains.data?.find((d) => d.key === domain);

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    submit.mutate();
  }

  if (submit.isSuccess) {
    return (
      <AuthLayout title="Check your e-mail">
        <div className="space-y-4">
          <Alert tone="success">
            We sent a link to <strong>{email}</strong>. Open it to finish creating your workspace. The link
            works once and expires in 24 hours.
          </Alert>
          <Link to="/login" className="block text-center text-sm font-medium text-brand-700 hover:underline">
            Back to sign in
          </Link>
        </div>
      </AuthLayout>
    );
  }

  if (step === "domain") {
    return (
      <AuthLayout title="Create your firm's workspace" subtitle="What kind of firm do you run?">
        {domains.isPending ? (
          <div className="flex justify-center py-8">
            <Spinner label="Loading" />
          </div>
        ) : domains.isError ? (
          <Alert tone="error">{errorMessage(domains.error)}</Alert>
        ) : (
          <div className="space-y-4">
            <div role="radiogroup" aria-label="Kind of firm" className="space-y-2">
              {domains.data.map((d) => {
                const selected = d.key === domain;
                return (
                  <button
                    key={d.key}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    onClick={() => setDomain(d.key)}
                    className={cx(
                      "flex w-full gap-3 rounded-lg border px-4 py-3 text-left focus:outline-none focus:ring-2 focus:ring-brand-500",
                      selected ? "border-brand-600 bg-brand-50" : "border-slate-200 hover:border-slate-300",
                    )}
                  >
                    <span aria-hidden="true" className="text-2xl leading-none">
                      {DOMAIN_ICONS[d.key]}
                    </span>
                    <span>
                      <span className="block font-medium text-slate-900">{d.label}</span>
                      <span className="block text-xs font-medium text-slate-500">{d.profession}</span>
                      <span className="mt-1 block text-sm text-slate-600">{d.description}</span>
                    </span>
                  </button>
                );
              })}
            </div>
            <Button className="w-full" disabled={!domain} onClick={() => setStep("details")}>
              Continue
            </Button>
            <p className="text-center text-sm text-slate-600">
              Already have a workspace?{" "}
              <Link to="/login" className="font-medium text-brand-700 hover:underline">
                Sign in
              </Link>
            </p>
          </div>
        )}
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Your firm's details"
      subtitle={
        <>
          {chosen?.label} workspace ·{" "}
          <button
            type="button"
            className="font-medium text-brand-700 hover:underline"
            onClick={() => setStep("domain")}
          >
            change
          </button>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {submit.isError && !fieldError(submit.error, "password") && (
          <Alert tone="error">{errorMessage(submit.error)}</Alert>
        )}
        <TextField
          label="Firm name"
          required
          autoComplete="organization"
          value={firm}
          onChange={(e) => setFirm(e.target.value)}
        />
        <TextField
          label="Your name"
          required
          autoComplete="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <TextField
          label="Work e-mail"
          type="email"
          required
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <TextField
          label="ABN (optional)"
          inputMode="numeric"
          value={abn}
          onChange={(e) => setAbn(e.target.value)}
        />
        <NewPasswordFields
          label="Password"
          password={password}
          confirm={confirm}
          onPassword={setPassword}
          onConfirm={setConfirm}
          serverError={fieldError(submit.error, "password")}
        />
        {/* Honeypot for bots: hidden from people and assistive technology. */}
        <div aria-hidden="true" className="hidden">
          <label>
            Website
            <input
              tabIndex={-1}
              autoComplete="off"
              value={honeypot}
              onChange={(e) => setHoneypot(e.target.value)}
            />
          </label>
        </div>
        <Checkbox
          label="I accept the terms of service and privacy policy. Client data is stored in Australia."
          checked={terms}
          onChange={(e) => setTerms(e.target.checked)}
        />
        <Button
          type="submit"
          className="w-full"
          loading={submit.isPending}
          disabled={!firm.trim() || !name.trim() || !email || !terms || !passwordsReady(password, confirm)}
        >
          Create workspace
        </Button>
      </form>
    </AuthLayout>
  );
}

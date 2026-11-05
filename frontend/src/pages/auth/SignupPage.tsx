import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState, type ComponentType, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { errorMessage, fieldError } from "../../api/client";
import { signupApi, type DomainKey, type DomainOption } from "../../api/signup";
import { useAuth } from "../../auth/context";
import { AuthLayout } from "../../components/AuthLayout";
import {
  CalculatorIcon,
  CheckIcon,
  ChevronLeftIcon,
  HomeIcon,
  MailIcon,
  PassportIcon,
  ScaleIcon,
} from "../../components/icons";
import { NewPasswordFields } from "../../components/NewPasswordFields";
import { Alert, Button, Checkbox, Spinner, TextField } from "../../components/ui";
import { cx } from "../../components/ui/cx";
import { isEmail, isValidAbn, passwordsReady } from "../../lib/password";
import { applyStoredBrandColor, previewBrandColor } from "../../lib/theme";

const DOMAIN_ICONS: Record<DomainKey, ComponentType<{ size?: number }>> = {
  legal: ScaleIcon,
  migration: PassportIcon,
  accounting: CalculatorIcon,
  lending: HomeIcon,
};

function StepLabel({ step }: { step: 1 | 2 }) {
  return (
    <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-brand-700">Step {step} of 2</p>
  );
}

function DomainAside({ domain }: { domain: DomainOption | undefined }) {
  if (!domain) return undefined;
  const Icon = DOMAIN_ICONS[domain.key];
  return (
    <>
      <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-white/15">
        <Icon size={24} />
      </span>
      <h2 className="mt-6 text-3xl font-semibold leading-tight tracking-tight">{domain.label} workspace</h2>
      <p className="mt-3 text-sm text-white/80">{domain.description}</p>
      <ul className="mt-8 space-y-3">
        {domain.includes.map((item) => (
          <li key={item} className="flex gap-3 text-sm text-white/90">
            <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white/15">
              <CheckIcon size={12} />
            </span>
            {item}
          </li>
        ))}
      </ul>
    </>
  );
}

/** Public sign-up: choose the kind of firm, then the firm and administrator details. */
export function SignupPage() {
  const domains = useQuery({
    queryKey: ["signup", "domains"],
    queryFn: ({ signal }) => signupApi.domains(signal),
    staleTime: Infinity,
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
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const navigate = useNavigate();
  const { refresh } = useAuth();
  const submit = useMutation({
    mutationFn: () =>
      signupApi.start({
        domain: domain!,
        firm_name: firm.trim(),
        name: name.trim(),
        email: email.trim(),
        password,
        abn: abn.trim() || null,
        accept_terms: terms,
        website_url: honeypot || null,
      }),
    onSuccess: async (result) => {
      // Created straight away (no e-mail set up on this install): signed in, so go to the workspace.
      if ("state" in result) {
        await refresh();
        navigate(result.state === "mfa_setup_required" ? "/mfa/setup?next=%2F" : "/", { replace: true });
      }
    },
  });
  const created = submit.data !== undefined && "state" in submit.data;
  const chosen = domains.data?.find((d) => d.key === domain);
  // Preview the profession's colour while choosing; restore the remembered one on leaving.
  useEffect(() => {
    if (chosen?.color) previewBrandColor(chosen.color);
  }, [chosen?.color]);
  useEffect(() => applyStoredBrandColor, []);
  const touch = (field: string) => () => setTouched((t) => ({ ...t, [field]: true }));

  const clientErrors = {
    firm_name: !firm.trim() ? "Enter your firm's name." : undefined,
    name: !name.trim() ? "Enter your name." : undefined,
    email: !isEmail(email) ? "Enter a valid e-mail address." : undefined,
    abn: abn.trim() && !isValidAbn(abn) ? "That isn't a valid ABN. Check the 11 digits." : undefined,
  };
  const shown = (field: keyof typeof clientErrors) =>
    (touched[field] ? clientErrors[field] : undefined) ?? fieldError(submit.error, field);
  const ready =
    !Object.values(clientErrors).some(Boolean) && terms && passwordsReady(password, confirm, { email, name });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    setTouched({ firm_name: true, name: true, email: true, abn: true });
    if (ready) submit.mutate();
  }

  // From the moment the form is sent: the workspace is being set up (usually about a second).
  if (created || submit.isPending) {
    const title = created ? "Opening your workspace" : `Setting up ${firm.trim() || "your workspace"}`;
    return (
      <AuthLayout title={title} aside={chosen ? <DomainAside domain={chosen} /> : undefined}>
        <div className="flex flex-col items-center gap-3 py-8 text-sm text-slate-600">
          <Spinner label={title} />
          <p>{created ? "Signing you in…" : `Preparing your ${chosen?.label ?? "workspace"}…`}</p>
        </div>
      </AuthLayout>
    );
  }

  if (submit.isSuccess) {
    return (
      <AuthLayout title="Check your inbox" aside={chosen ? <DomainAside domain={chosen} /> : undefined}>
        <div className="space-y-6">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-50 text-brand-700">
            <MailIcon size={24} />
          </div>
          <p className="text-sm leading-relaxed text-slate-700">
            We sent a confirmation link to <strong className="text-slate-900">{email}</strong>. Open it to
            create your workspace — it works once and expires in 24 hours.
          </p>
          <p className="text-sm text-slate-600">
            Nothing arrived? Check your spam folder, or{" "}
            <button
              type="button"
              className="font-medium text-brand-700 hover:underline disabled:opacity-50"
              disabled={submit.isPending}
              onClick={() => submit.mutate()}
            >
              send it again
            </button>
            .
          </p>
          <Link to="/login" className="block text-sm font-medium text-brand-700 hover:underline">
            Back to sign in
          </Link>
        </div>
      </AuthLayout>
    );
  }

  if (step === "domain") {
    return (
      <AuthLayout
        wide
        title="What kind of firm do you run?"
        subtitle="We'll set up your workspace with the right records, workflows and compliance checks."
        aside={chosen ? <DomainAside domain={chosen} /> : undefined}
      >
        <StepLabel step={1} />
        {domains.isPending ? (
          <div className="flex justify-center py-12">
            <Spinner label="Loading" />
          </div>
        ) : domains.isError ? (
          <Alert tone="error">
            {errorMessage(domains.error)}{" "}
            <button type="button" className="font-medium underline" onClick={() => void domains.refetch()}>
              Try again
            </button>
          </Alert>
        ) : (
          <div className="space-y-6">
            <div role="radiogroup" aria-label="Kind of firm" className="grid gap-3 sm:grid-cols-2">
              {domains.data.map((d) => {
                const selected = d.key === domain;
                const Icon = DOMAIN_ICONS[d.key];
                return (
                  <button
                    key={d.key}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    onClick={() => setDomain(d.key)}
                    onDoubleClick={() => {
                      setDomain(d.key);
                      setStep("details");
                    }}
                    className={cx(
                      "group relative flex flex-col gap-3 rounded-xl border p-4 text-left transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500",
                      selected
                        ? "border-brand-600 bg-brand-50/60 ring-1 ring-brand-600"
                        : "border-slate-200 hover:border-slate-300 hover:bg-slate-50",
                    )}
                  >
                    <span
                      className={cx(
                        "flex h-10 w-10 items-center justify-center rounded-lg transition",
                        selected
                          ? "bg-brand-700 text-white"
                          : "bg-slate-100 text-slate-600 group-hover:bg-slate-200",
                      )}
                    >
                      <Icon size={20} />
                    </span>
                    <span>
                      <span className="block font-medium text-slate-900">{d.label}</span>
                      <span className="mt-0.5 block text-xs text-slate-500">{d.profession}</span>
                    </span>
                    {selected && (
                      <span className="absolute right-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-brand-700 text-white">
                        <CheckIcon size={12} />
                      </span>
                    )}
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

  const bannerError =
    submit.isError &&
    !["password", "email", "abn", "firm_name", "name"].some((f) => fieldError(submit.error, f));

  return (
    <AuthLayout
      title="Tell us about your firm"
      subtitle={
        <button
          type="button"
          className="inline-flex items-center gap-1 font-medium text-brand-700 hover:underline"
          onClick={() => setStep("domain")}
        >
          <ChevronLeftIcon size={14} />
          {chosen?.label ?? "Change firm type"}
        </button>
      }
      aside={chosen ? <DomainAside domain={chosen} /> : undefined}
    >
      <StepLabel step={2} />
      <form onSubmit={onSubmit} className="space-y-5" noValidate>
        {bannerError && <Alert tone="error">{errorMessage(submit.error)}</Alert>}
        <TextField
          label="Firm name"
          required
          autoFocus
          autoComplete="organization"
          value={firm}
          onChange={(e) => setFirm(e.target.value)}
          onBlur={touch("firm_name")}
          error={shown("firm_name")}
        />
        <div className="grid gap-5 sm:grid-cols-2">
          <TextField
            label="Your name"
            required
            autoComplete="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onBlur={touch("name")}
            error={shown("name")}
          />
          <TextField
            label="ABN (optional)"
            inputMode="numeric"
            placeholder="51 824 753 556"
            value={abn}
            onChange={(e) => setAbn(e.target.value)}
            onBlur={touch("abn")}
            error={shown("abn")}
          />
        </div>
        <TextField
          label="Work e-mail"
          type="email"
          required
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          onBlur={touch("email")}
          error={shown("email")}
        />
        <NewPasswordFields
          label="Password"
          password={password}
          confirm={confirm}
          onPassword={setPassword}
          onConfirm={setConfirm}
          serverError={fieldError(submit.error, "password")}
          email={email}
          name={name}
        />
        {/* Honeypot for bots: hidden from people and assistive technology. Deliberately not named or
            labelled like anything a browser or password manager autofills (a filled honeypot drops the
            sign-up silently). */}
        <div aria-hidden="true" className="hidden">
          <label>
            Leave this field empty
            <input
              name="contact_me_by_fax_only"
              tabIndex={-1}
              autoComplete="off"
              value={honeypot}
              onChange={(e) => setHoneypot(e.target.value)}
            />
          </label>
        </div>
        <Checkbox
          label={<>I agree to the terms of service and privacy policy.</>}
          checked={terms}
          onChange={(e) => setTerms(e.target.checked)}
        />
        <Button type="submit" className="w-full" loading={submit.isPending} disabled={!ready}>
          Create workspace
        </Button>
      </form>
    </AuthLayout>
  );
}

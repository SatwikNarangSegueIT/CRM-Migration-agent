import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, errorMessage } from "../../api/client";
import { recordsApi } from "../../api/records";
import type { RecordData } from "../../api/types";
import { recordPath, useApps } from "../../lib/records";
import { Alert, Button, Checkbox, FormField, Input } from "../ui";
import { Modal } from "../ui/Modal";
import { Combobox, controlClass } from "./FieldInput";

type ParamSpec = {
  name: string;
  label: string;
  type: "text" | "textarea" | "datetime" | "date" | "segment";
  required?: boolean;
  hint?: string;
};

// Actions that need input before they run. Other actions just confirm.
const ACTION_PARAMS: Record<string, ParamSpec[]> = {
  "invoice.void": [{ name: "reason", label: "Reason for voiding", type: "textarea", required: true }],
  "payment.reverse": [{ name: "reason", label: "Reason for the reversal", type: "textarea", required: true }],
  "case.close": [{ name: "resolution", label: "Resolution", type: "textarea", required: true }],
  "matter.lodge": [
    { name: "immi_trn", label: "ImmiAccount TRN", type: "text", required: true },
    { name: "lodgement_date", label: "Lodgement date", type: "date" },
  ],
  "matter.override_agreement_gate": [
    { name: "reason", label: "Reason (recorded in the audit log)", type: "textarea", required: true },
  ],
  "legal_time_entry.write_off": [
    {
      name: "reason",
      label: "Reason for the write-off (recorded in the audit log)",
      type: "textarea",
      required: true,
    },
  ],
  "email_send.schedule": [
    { name: "scheduled_at", label: "Send at", type: "datetime", hint: "Leave empty to send now." },
  ],
  "campaign.add_members": [
    { name: "segment_id", label: "Add everyone in segment", type: "segment", required: true },
  ],
};

const CONFIRM_TEXT: Record<string, string> = {
  "invoice.issue": "Issuing assigns the next invoice number and locks the lines.",
  "quote.create_invoice": "A draft invoice is created with the quote's lines.",
  "service_agreement.send": "The agreement is marked as sent; the client can sign it in the portal.",
  "email_send.cancel": "The scheduled e-mail won't be sent.",
  "case.accept": "You become the owner of this case.",
  "legal_matter.bill_time": "A draft invoice is created with a line for each unbilled time entry.",
  "conflict_check.run_search": "Searches clients, organisations and other matters' parties again.",
  "engagement.create_invoice": "A draft invoice is created for the agreed fee (or the unbilled time).",
  "engagement_letter.send": "The letter is marked as sent; the client can sign it in the portal.",
  "account.generate_bas_deadlines": "Creates this financial year's activity statement deadlines.",
  "loan_application.record_assessment":
    "Records the preliminary assessment and locks the Best Interests Duty record.",
};

export function ActionDialog({
  object,
  record,
  action,
  onClose,
  onDone,
}: {
  object: string;
  record: RecordData;
  action: { name: string; label: string } | null;
  onClose: () => void;
  onDone: (result: Record<string, unknown>) => void;
}) {
  const key = action ? `${object}.${action.name}` : "";
  if (!action) return null;
  if (key === "lead.convert") return <ConvertLeadDialog record={record} onClose={onClose} onDone={onDone} />;
  return (
    <GenericActionDialog
      key={key}
      object={object}
      record={record}
      action={action}
      specKey={key}
      onClose={onClose}
      onDone={onDone}
    />
  );
}

function GenericActionDialog({
  object,
  record,
  action,
  specKey,
  onClose,
  onDone,
}: {
  object: string;
  record: RecordData;
  action: { name: string; label: string };
  specKey: string;
  onClose: () => void;
  onDone: (result: Record<string, unknown>) => void;
}) {
  const spec = ACTION_PARAMS[specKey] ?? [];
  const [values, setValues] = useState<Record<string, string>>({});
  const [segmentName, setSegmentName] = useState("");
  const run = useMutation({
    mutationFn: () => {
      const payload: Record<string, unknown> = {};
      for (const p of spec) {
        const v = values[p.name];
        if (!v) continue;
        payload[p.name] = p.type === "datetime" ? new Date(v).toISOString() : v;
      }
      return recordsApi.action(object, record.id, action.name, payload);
    },
    onSuccess: onDone,
  });
  const err = run.error instanceof ApiError ? run.error : null;
  const missing = spec.some((p) => p.required && !values[p.name]);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    run.mutate();
  }
  return (
    <Modal
      open
      onClose={onClose}
      title={action.label}
      size="sm"
      busy={run.isPending}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={run.isPending}>
            Cancel
          </Button>
          <Button type="submit" form="action-form" loading={run.isPending} disabled={missing}>
            {action.label}
          </Button>
        </>
      }
    >
      <form id="action-form" onSubmit={onSubmit} className="space-y-4" noValidate>
        {err && <Alert tone="error">{errorMessage(err)}</Alert>}
        {spec.length === 0 && (
          <p className="text-sm text-slate-700">
            {CONFIRM_TEXT[specKey] ?? `Run "${action.label}" on ${record.name}?`}
          </p>
        )}
        {spec.map((p) => (
          <FormField
            key={p.name}
            label={p.label}
            required={p.required}
            hint={p.hint}
            error={err?.fields[p.name]}
          >
            {({ id, describedBy, invalid }) =>
              p.type === "textarea" ? (
                <textarea
                  id={id}
                  rows={4}
                  aria-describedby={describedBy}
                  className={controlClass(invalid)}
                  value={values[p.name] ?? ""}
                  onChange={(e) => setValues((v) => ({ ...v, [p.name]: e.target.value }))}
                />
              ) : p.type === "segment" ? (
                <Combobox
                  id={id}
                  value={values[p.name] ?? null}
                  displayName={segmentName}
                  onChange={(v, name) => {
                    setValues((cur) => ({ ...cur, [p.name]: v ?? "" }));
                    setSegmentName(name ?? "");
                  }}
                  search={(q, signal) => recordsApi.lookup("segment", q, signal)}
                  queryKey={["lookup", "segment"]}
                />
              ) : (
                <Input
                  id={id}
                  aria-describedby={describedBy}
                  invalid={invalid}
                  type={p.type === "datetime" ? "datetime-local" : p.type === "date" ? "date" : "text"}
                  value={values[p.name] ?? ""}
                  onChange={(e) => setValues((v) => ({ ...v, [p.name]: e.target.value }))}
                />
              )
            }
          </FormField>
        ))}
      </form>
    </Modal>
  );
}

function ConvertLeadDialog({
  record,
  onClose,
  onDone,
}: {
  record: RecordData;
  onClose: () => void;
  onDone: (result: Record<string, unknown>) => void;
}) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const dupes = useQuery({
    queryKey: ["convert-dupes", record.id],
    queryFn: () =>
      recordsApi.action("lead", record.id, "convert", { check_duplicates: true }) as Promise<{
        duplicates: { accounts: { id: string; name: string }[]; contacts: { id: string; name: string }[] };
      }>,
  });
  const [accountId, setAccountId] = useState("");
  const [contactId, setContactId] = useState("");
  // Offer an opportunity only where a visible app uses them (not in law, migration, accounting or
  // lending workspaces, which hide the Sales app).
  const apps = useApps();
  const opportunities = (apps.data ?? []).some((a) =>
    a.tabs.some((t) => t.kind === "object" && t.object === "opportunity"),
  );
  const [createOpp, setCreateOpp] = useState(true);
  const withOpp = opportunities && createOpp;
  // The workspace's words for these records (e.g. Client / Organisation / Enquiry in a law firm).
  const tabLabel = (api: string, fallback: string) =>
    (apps.data ?? []).flatMap((a) => a.tabs).find((t) => t.kind === "object" && t.object === api)?.label ??
    fallback;
  const plural = { account: tabLabel("account", "Accounts"), contact: tabLabel("contact", "Contacts") };
  const singular = (p: string) =>
    p.endsWith("People")
      ? p.slice(0, -6) + "Person"
      : p.endsWith("ies")
        ? p.slice(0, -3) + "y"
        : p.replace(/s$/, "");
  const accountWord = singular(plural.account);
  const contactWord = singular(plural.contact);
  // An individual (no company) in a profession workspace isn't given an organisation named after them.
  const individual = !record.fields.company && !opportunities;
  const company = String(record.fields.company ?? record.name);
  const [oppName, setOppName] = useState(`${company} -`);
  const convert = useMutation({
    mutationFn: () =>
      recordsApi.action("lead", record.id, "convert", {
        account_id: accountId || undefined,
        contact_id: contactId || undefined,
        create_opportunity: withOpp,
        opportunity_name: oppName,
      }),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["records"] });
      onDone(result);
      const target = (result.opportunity_id as string) || (result.contact_id as string);
      navigate(recordPath(result.opportunity_id ? "opportunity" : "contact", target));
    },
  });
  const d = dupes.data?.duplicates;
  return (
    <Modal
      open
      onClose={onClose}
      title={`Convert ${record.name}`}
      busy={convert.isPending}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => convert.mutate()} loading={convert.isPending}>
            Convert
          </Button>
        </>
      }
    >
      <div className="space-y-5 text-sm">
        {convert.isError && <Alert tone="error">{errorMessage(convert.error)}</Alert>}
        <section>
          <h3 className="font-semibold text-slate-900">{accountWord}</h3>
          <label className="mt-2 flex items-center gap-2">
            <input type="radio" name="account" checked={accountId === ""} onChange={() => setAccountId("")} />
            {individual ? (
              <>No {accountWord.toLowerCase()}: an individual</>
            ) : (
              <>
                Create new {accountWord.toLowerCase()} <strong>{company}</strong>
              </>
            )}
          </label>
          {d?.accounts.map((a) => (
            <label key={a.id} className="mt-1 flex items-center gap-2">
              <input
                type="radio"
                name="account"
                checked={accountId === a.id}
                onChange={() => setAccountId(a.id)}
              />
              Use existing {accountWord.toLowerCase()} <strong>{a.name}</strong>
            </label>
          ))}
        </section>
        <section>
          <h3 className="font-semibold text-slate-900">{contactWord}</h3>
          <label className="mt-2 flex items-center gap-2">
            <input type="radio" name="contact" checked={contactId === ""} onChange={() => setContactId("")} />
            Create new {contactWord.toLowerCase()} <strong>{record.name}</strong>
          </label>
          {d?.contacts.map((c) => (
            <label key={c.id} className="mt-1 flex items-center gap-2">
              <input
                type="radio"
                name="contact"
                checked={contactId === c.id}
                onChange={() => setContactId(c.id)}
              />
              Use existing {contactWord.toLowerCase()} <strong>{c.name}</strong> (same e-mail)
            </label>
          ))}
        </section>
        {opportunities && (
          <section>
            <h3 className="font-semibold text-slate-900">Opportunity</h3>
            <div className="mt-2">
              <Checkbox
                label="Create an opportunity"
                checked={createOpp}
                onChange={(e) => setCreateOpp(e.target.checked)}
              />
            </div>
            {createOpp && (
              <div className="mt-2">
                <label htmlFor="opp-name" className="block text-sm font-medium text-slate-700">
                  Opportunity name
                </label>
                <input
                  id="opp-name"
                  className={controlClass(false, "mt-1")}
                  value={oppName}
                  onChange={(e) => setOppName(e.target.value)}
                />
              </div>
            )}
          </section>
        )}
        <p className="text-xs text-slate-500">
          Activities and consent move to the new {contactWord.toLowerCase()}. This record becomes read-only.
        </p>
      </div>
    </Modal>
  );
}

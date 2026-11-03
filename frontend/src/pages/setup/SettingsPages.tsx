// Setup → Settings: company & branding, billing, service levels, marketing and data retention.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { errorMessage } from "../../api/client";
import { setupApi } from "../../api/setup";
import { useAuth } from "../../auth/context";
import { SettingsIcon } from "../../components/icons";
import { controlClass } from "../../components/record/FieldInput";
import {
  Alert,
  Button,
  Checkbox,
  FormField,
  Input,
  PageHeader,
  Spinner,
  useToast,
} from "../../components/ui";
import { useObjects } from "../../lib/records";
import { NotFoundPage } from "../NotFoundPage";

type Kind =
  | "text"
  | "textarea"
  | "number"
  | "checkbox"
  | "color"
  | "url"
  | "email"
  | "select"
  | "readonly"
  | "object_years";
type Field = {
  key: string;
  label: string;
  kind: Kind;
  hint?: string;
  options?: { value: string; label: string }[];
};
type Group = { setting: string; title: string; description?: string; fields: Field[]; writePerm: string[] };

const BILLING_PERMS = ["manage_billing_settings"];
const COMPANY_PERMS = ["manage_billing_settings", "customize_application"];
const CUSTOMIZE = ["customize_application"];

const SECTIONS: Record<string, { title: string; subtitle: string; groups: Group[] }> = {
  company: {
    title: "Company & Branding",
    subtitle: "Your organisation's identity on screens, documents, e-mails and the customer portal.",
    groups: [
      {
        setting: "branding",
        title: "Branding",
        writePerm: CUSTOMIZE,
        fields: [
          {
            key: "name",
            label: "Product name",
            kind: "text",
            hint: "Shown in the header, portal and e-mails.",
          },
          { key: "primary_color", label: "Primary colour", kind: "color" },
          { key: "logo_url", label: "Logo URL", kind: "url", hint: "HTTPS link to a PNG or SVG logo." },
        ],
      },
      {
        setting: "company",
        title: "Company details",
        description: "Printed on quotes and tax invoices.",
        writePerm: COMPANY_PERMS,
        fields: [
          { key: "legal_name", label: "Legal name", kind: "text" },
          { key: "abn", label: "ABN", kind: "text", hint: "11-digit Australian Business Number." },
          { key: "address", label: "Address", kind: "textarea" },
          { key: "email", label: "E-mail", kind: "email" },
          { key: "phone", label: "Phone", kind: "text" },
          { key: "website", label: "Website", kind: "url" },
        ],
      },
      {
        setting: "locale",
        title: "Locale",
        writePerm: CUSTOMIZE,
        fields: [
          {
            key: "default_locale",
            label: "Default locale",
            kind: "select",
            options: [
              { value: "en-AU", label: "English (Australia)" },
              { value: "en-NZ", label: "English (New Zealand)" },
              { value: "en-GB", label: "English (United Kingdom)" },
              { value: "en-US", label: "English (United States)" },
            ],
          },
          {
            key: "default_time_zone",
            label: "Default time zone",
            kind: "text",
            hint: "IANA name, e.g. Australia/Sydney.",
          },
          { key: "currency", label: "Currency", kind: "readonly", hint: "Single currency in this version." },
        ],
      },
    ],
  },
  billing: {
    title: "Billing",
    subtitle: "Invoice numbering, payment terms and GST. Tax rates are records in the Tax Rates tab.",
    groups: [
      {
        setting: "billing",
        title: "Invoices",
        writePerm: BILLING_PERMS,
        fields: [
          { key: "invoice_prefix", label: "Invoice number prefix", kind: "text" },
          { key: "invoice_number_digits", label: "Invoice number digits", kind: "number" },
          { key: "payment_terms_days", label: "Payment terms (days)", kind: "number" },
          {
            key: "gst_registered",
            label: "Registered for GST (shows “Tax Invoice” and ABN)",
            kind: "checkbox",
          },
          {
            key: "bank_details",
            label: "Bank details",
            kind: "textarea",
            hint: "Printed on invoices for payment by transfer.",
          },
          { key: "invoice_footer", label: "Invoice footer", kind: "textarea" },
        ],
      },
    ],
  },
  service: {
    title: "Service Levels",
    subtitle: "Case SLA targets by priority and public web forms.",
    groups: [
      {
        setting: "service",
        title: "Web forms",
        writePerm: CUSTOMIZE,
        fields: [
          {
            key: "web_to_case_enabled",
            label: "Accept cases from the public web-to-case form",
            kind: "checkbox",
          },
          {
            key: "web_to_lead_enabled",
            label: "Accept leads from the public web-to-lead form",
            kind: "checkbox",
          },
        ],
      },
    ],
  },
  marketing: {
    title: "Marketing",
    subtitle: "Sender identity and delivery settings for e-mail sends (required by the Spam Act 2003).",
    groups: [
      {
        setting: "marketing",
        title: "Sender",
        writePerm: CUSTOMIZE,
        fields: [
          { key: "from_name", label: "From name", kind: "text" },
          { key: "from_email", label: "From e-mail", kind: "email" },
          {
            key: "postal_address",
            label: "Postal address",
            kind: "textarea",
            hint: "Included in every marketing e-mail.",
          },
          { key: "batch_size", label: "Batch size", kind: "number", hint: "E-mails sent per worker batch." },
        ],
      },
    ],
  },
  retention: {
    title: "Data Retention",
    subtitle: "How long deleted data and history are kept.",
    groups: [
      {
        setting: "retention",
        title: "Retention",
        writePerm: CUSTOMIZE,
        fields: [
          {
            key: "recycle_bin_days",
            label: "Recycle bin (days)",
            kind: "number",
            hint: "Deleted records can be restored for this long.",
          },
          { key: "deleted_field_days", label: "Deleted fields (days)", kind: "number" },
          {
            key: "audit_years",
            label: "Audit log (years)",
            kind: "number",
            hint: "Record-keeping obligations often require 7 years.",
          },
          {
            key: "object_years",
            label: "Retention policies by object",
            kind: "object_years",
            hint: "Records not changed for this many years move to the recycle bin (a nightly job). Leave blank to keep forever.",
          },
        ],
      },
    ],
  },
};

type Settings = Record<string, Record<string, unknown>>;

function ObjectYearsEditor({
  label,
  hint,
  value,
  disabled,
  onChange,
}: {
  label: string;
  hint?: string;
  value: Record<string, number>;
  disabled: boolean;
  onChange: (v: Record<string, number>) => void;
}) {
  const objects = useObjects();
  const list = (objects.data ?? []).filter((o) => !o.is_detail_only);
  return (
    <fieldset>
      <legend className="text-sm font-medium text-slate-700">{label}</legend>
      {hint && <p className="text-xs text-slate-500">{hint}</p>}
      <div className="mt-2 grid max-h-72 gap-x-6 gap-y-1 overflow-y-auto sm:grid-cols-2">
        {list.map((o) => (
          <label key={o.api_name} className="flex items-center justify-between gap-2 text-sm">
            <span>{o.plural_label}</span>
            <input
              type="number"
              min={1}
              max={50}
              aria-label={`Retention for ${o.plural_label} (years)`}
              disabled={disabled}
              className={controlClass(false, "w-24 py-1")}
              value={value[o.api_name] ?? ""}
              onChange={(e) => {
                const next = { ...value };
                if (e.target.value) next[o.api_name] = Number(e.target.value);
                else delete next[o.api_name];
                onChange(next);
              }}
            />
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function SettingGroup({
  group,
  value,
  onSaved,
}: {
  group: Group;
  value: Record<string, unknown>;
  onSaved: (v: Record<string, unknown>) => void;
}) {
  const { can } = useAuth();
  const toast = useToast();
  const editable = group.writePerm.some(can);
  const [form, setForm] = useState<Record<string, unknown>>(value);
  const save = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = {};
      for (const f of group.fields) {
        if (f.kind === "readonly") continue;
        const v = form[f.key];
        body[f.key] =
          f.kind === "number"
            ? Number(v)
            : f.kind === "url" || f.kind === "email"
              ? String(v ?? "").trim() || (f.key === "logo_url" ? null : "")
              : v;
      }
      return setupApi.saveSetting(group.setting, body);
    },
    onSuccess: (v) => {
      onSaved(v);
      toast.show(`${group.title} saved.`);
    },
  });
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="font-semibold text-slate-900">{group.title}</h2>
      {group.description && <p className="text-xs text-slate-600">{group.description}</p>}
      {save.isError && (
        <Alert tone="error" className="mt-3">
          {errorMessage(save.error)}
        </Alert>
      )}
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {group.fields.map((f) => {
          const v = form[f.key];
          if (f.kind === "object_years")
            return (
              <div key={f.key} className="sm:col-span-2">
                <ObjectYearsEditor
                  label={f.label}
                  hint={f.hint}
                  disabled={!editable}
                  value={(v as Record<string, number> | undefined) ?? {}}
                  onChange={(next) => setForm({ ...form, [f.key]: next })}
                />
              </div>
            );
          if (f.kind === "checkbox")
            return (
              <div key={f.key} className="sm:col-span-2">
                <Checkbox
                  label={f.label}
                  disabled={!editable}
                  checked={Boolean(v)}
                  onChange={(e) => setForm({ ...form, [f.key]: e.target.checked })}
                />
              </div>
            );
          return (
            <div key={f.key} className={f.kind === "textarea" ? "sm:col-span-2" : undefined}>
              <FormField label={f.label} hint={f.hint}>
                {({ id }) =>
                  f.kind === "textarea" ? (
                    <textarea
                      id={id}
                      rows={3}
                      disabled={!editable}
                      className={controlClass(false)}
                      value={String(v ?? "")}
                      onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                    />
                  ) : f.kind === "select" ? (
                    <select
                      id={id}
                      disabled={!editable}
                      className={controlClass(false)}
                      value={String(v ?? "")}
                      onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                    >
                      {f.options?.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                  ) : f.kind === "color" ? (
                    <input
                      id={id}
                      type="color"
                      disabled={!editable}
                      className="h-9 w-16 rounded border border-slate-300"
                      value={String(v || "#0176d3")}
                      onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                    />
                  ) : f.kind === "readonly" ? (
                    <p id={id} className="mt-1 text-sm">
                      {String(v ?? "")}
                    </p>
                  ) : (
                    <Input
                      id={id}
                      disabled={!editable}
                      type={
                        f.kind === "number"
                          ? "number"
                          : f.kind === "email"
                            ? "email"
                            : f.kind === "url"
                              ? "url"
                              : "text"
                      }
                      value={v === null || v === undefined ? "" : String(v)}
                      onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                    />
                  )
                }
              </FormField>
            </div>
          );
        })}
      </div>
      {editable && (
        <div className="mt-4 flex justify-end">
          <Button onClick={() => save.mutate()} loading={save.isPending}>
            Save
          </Button>
        </div>
      )}
    </section>
  );
}

const PRIORITIES = ["Critical", "High", "Medium", "Low"];

function SlaGroup({
  value,
  onSaved,
}: {
  value: Record<string, unknown>;
  onSaved: (v: Record<string, unknown>) => void;
}) {
  const { can } = useAuth();
  const toast = useToast();
  const editable = can("customize_application");
  const toRows = (v: Record<string, unknown>) =>
    Object.fromEntries(
      PRIORITIES.map((p) => {
        const sla = (v[p] ?? {}) as { first_response_hours?: number; resolution_hours?: number };
        return [
          p,
          { first: String(sla.first_response_hours ?? ""), resolution: String(sla.resolution_hours ?? "") },
        ];
      }),
    );
  const [rows, setRows] = useState(toRows(value));
  const save = useMutation({
    mutationFn: () =>
      setupApi.saveSetting(
        "case_sla",
        Object.fromEntries(
          PRIORITIES.map((p) => [
            p,
            { first_response_hours: Number(rows[p]!.first), resolution_hours: Number(rows[p]!.resolution) },
          ]),
        ),
      ),
    onSuccess: (v) => {
      onSaved(v);
      toast.show("Service levels saved.");
    },
  });
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="font-semibold text-slate-900">Case SLA targets</h2>
      <p className="text-xs text-slate-600">
        New cases get first-response and resolution due dates from their priority. Overdue cases are escalated
        automatically.
      </p>
      {save.isError && (
        <Alert tone="error" className="mt-3">
          {errorMessage(save.error)}
        </Alert>
      )}
      <table className="mt-3 text-sm">
        <thead>
          <tr className="text-left text-xs text-slate-600">
            <th className="py-1 pr-6">Priority</th>
            <th className="py-1 pr-6">First response (hours)</th>
            <th className="py-1">Resolution (hours)</th>
          </tr>
        </thead>
        <tbody>
          {PRIORITIES.map((p) => (
            <tr key={p}>
              <td className="py-1 pr-6 font-medium">{p}</td>
              <td className="py-1 pr-6">
                <Input
                  aria-label={`${p} first response hours`}
                  type="number"
                  min={0.25}
                  step="any"
                  className="w-32"
                  disabled={!editable}
                  value={rows[p]!.first}
                  onChange={(e) => setRows({ ...rows, [p]: { ...rows[p]!, first: e.target.value } })}
                />
              </td>
              <td className="py-1">
                <Input
                  aria-label={`${p} resolution hours`}
                  type="number"
                  min={0.25}
                  step="any"
                  className="w-32"
                  disabled={!editable}
                  value={rows[p]!.resolution}
                  onChange={(e) => setRows({ ...rows, [p]: { ...rows[p]!, resolution: e.target.value } })}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {editable && (
        <div className="mt-4 flex justify-end">
          <Button onClick={() => save.mutate()} loading={save.isPending}>
            Save
          </Button>
        </div>
      )}
    </section>
  );
}

function WebQueueGroup({
  value,
  onSaved,
}: {
  value: Record<string, unknown>;
  onSaved: (v: Record<string, unknown>) => void;
}) {
  const { can } = useAuth();
  const toast = useToast();
  const editable = can("customize_application");
  const queues = useQuery({
    queryKey: ["setup", "queues"],
    queryFn: ({ signal }) => setupApi.queues(signal),
  });
  const [queueId, setQueueId] = useState(String(value.web_queue_id ?? ""));
  const save = useMutation({
    mutationFn: () => setupApi.saveSetting("service", { web_queue_id: queueId || null }),
    onSuccess: (v) => {
      onSaved(v);
      toast.show("Queue saved.");
    },
  });
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="font-semibold text-slate-900">Web and portal case queue</h2>
      <p className="text-xs text-slate-600">
        Cases from the web form and the customer portal are owned by this queue. Manage queues in{" "}
        <Link to="/setup/groups" className="text-brand-700 hover:underline">
          Public Groups & Queues
        </Link>
        .
      </p>
      {save.isError && (
        <Alert tone="error" className="mt-3">
          {errorMessage(save.error)}
        </Alert>
      )}
      <div className="mt-3 flex items-end gap-2">
        <FormField label="Queue">
          {({ id }) => (
            <select
              id={id}
              disabled={!editable}
              className={controlClass(false)}
              value={queueId}
              onChange={(e) => setQueueId(e.target.value)}
            >
              <option value="">Default (Customer Support)</option>
              {(queues.data ?? [])
                .filter((q) => q.object_api_names.includes("case"))
                .map((q) => (
                  <option key={q.id} value={q.id}>
                    {q.name}
                  </option>
                ))}
            </select>
          )}
        </FormField>
        {editable && (
          <Button onClick={() => save.mutate()} loading={save.isPending}>
            Save
          </Button>
        )}
      </div>
    </section>
  );
}

export function SettingsPage() {
  const { section = "" } = useParams();
  const qc = useQueryClient();
  const config = SECTIONS[section];
  const settings = useQuery({
    queryKey: ["setup", "settings"],
    queryFn: ({ signal }) => setupApi.settings(signal),
    enabled: Boolean(config),
  });
  if (!config) return <NotFoundPage />;
  const saved = (key: string) => (v: Record<string, unknown>) => {
    qc.setQueryData<Settings>(["setup", "settings"], (old) => ({ ...(old ?? {}), [key]: v }));
    void qc.invalidateQueries({ queryKey: ["meta", "settings"] });
    void qc.invalidateQueries({ queryKey: ["branding"] });
  };
  return (
    <div>
      <PageHeader
        breadcrumbs={[{ label: "Setup", to: "/setup" }]}
        title={config.title}
        subtitle={config.subtitle}
        icon={<SettingsIcon size={22} className="text-brand-700" />}
      />
      {settings.isPending ? (
        <Spinner label="Loading settings" />
      ) : settings.isError ? (
        <Alert tone="error">{errorMessage(settings.error)}</Alert>
      ) : (
        <div className="space-y-4">
          {section === "service" && (
            <SlaGroup
              key={JSON.stringify(settings.data.case_sla ?? {})}
              value={settings.data.case_sla ?? {}}
              onSaved={saved("case_sla")}
            />
          )}
          {section === "service" && (
            <WebQueueGroup
              key={JSON.stringify(settings.data.service ?? {})}
              value={settings.data.service ?? {}}
              onSaved={saved("service")}
            />
          )}
          {config.groups.map((g) => (
            <SettingGroup
              // Remount with the saved value so the form never shows stale data.
              key={`${g.setting}:${JSON.stringify(settings.data[g.setting] ?? {})}`}
              group={g}
              value={settings.data[g.setting] ?? {}}
              onSaved={saved(g.setting)}
            />
          ))}
          {section === "billing" && (
            <p className="text-sm text-slate-600">
              Tax rates (e.g. GST 10%, GST-free) are managed as records in{" "}
              <Link to="/o/tax_rate" className="text-brand-700 hover:underline">
                Tax Rates
              </Link>
              .
            </p>
          )}
        </div>
      )}
    </div>
  );
}

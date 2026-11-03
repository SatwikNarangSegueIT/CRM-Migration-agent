// Setup → Object Manager: standard and custom objects, fields, picklists and layouts (plan v3 §4).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, errorMessage } from "../../api/client";
import { setupApi, type SetupObject, type SetupObjectSummary } from "../../api/setup";
import type { FieldDescribe, LayoutSection, PicklistValue } from "../../api/types";
import { useAuth } from "../../auth/context";
import { ArrowRightIcon, LayersIcon, PlusIcon, TrashIcon } from "../../components/icons";
import { controlClass } from "../../components/record/FieldInput";
import { ObjectIcon } from "../../components/record/ObjectIcon";
import {
  Alert,
  Badge,
  Button,
  Checkbox,
  ConfirmDialog,
  FormField,
  Input,
  PageHeader,
  Spinner,
  useToast,
} from "../../components/ui";
import { cx } from "../../components/ui/cx";
import { Modal } from "../../components/ui/Modal";
import { formatDateTimeValue } from "../../lib/records";

export const ICON_CHOICES = [
  "custom",
  "account",
  "contact",
  "lead",
  "opportunity",
  "product",
  "quote",
  "invoice",
  "case",
  "campaign",
  "segment",
  "template",
  "task",
  "event",
  "note",
  "file",
  "matter",
  "checklist",
  "agreement",
  "ledger",
  "passport",
  "sales",
  "service",
  "marketing",
  "billing",
  "analytics",
  "dashboard",
];

export const FIELD_TYPE_LABELS: Record<string, string> = {
  text: "Text",
  textarea: "Text Area",
  long_text: "Long Text Area",
  email: "Email",
  phone: "Phone",
  url: "URL",
  number: "Number",
  percent: "Percent",
  currency: "Currency",
  date: "Date",
  datetime: "Date/Time",
  time: "Time",
  checkbox: "Checkbox",
  picklist: "Picklist",
  multi_picklist: "Picklist (Multi-Select)",
  lookup: "Lookup Relationship",
  master_detail: "Master-Detail Relationship",
  auto_number: "Auto Number",
  address: "Address",
  encrypted_text: "Text (Encrypted)",
  user: "User",
  id: "Record ID",
  owner: "Owner",
};

const OBJECT_FLAGS: { key: keyof SetupObject; label: string; hint: string }[] = [
  {
    key: "track_history",
    label: "Track field history",
    hint: "Fields marked 'track history' record old and new values.",
  },
  {
    key: "allow_activities",
    label: "Allow activities",
    hint: "Tasks and events can be related to these records.",
  },
  { key: "allow_notes", label: "Allow notes", hint: "Notes can be added on record pages." },
  { key: "allow_files", label: "Allow files", hint: "Files can be attached to records." },
  { key: "searchable", label: "Allow search", hint: "Records appear in global search." },
  { key: "allow_reports", label: "Allow reports", hint: "The object can be used in report types." },
  { key: "allow_queues", label: "Allow queues", hint: "Records can be owned by a queue." },
  {
    key: "show_in_portal",
    label: "Show in customer portal",
    hint: "Portal users may see records shared with them.",
  },
];

const LENGTH_TYPES = new Set(["text", "textarea", "long_text", "encrypted_text"]);
const NUMERIC_TYPES = new Set(["number", "percent", "currency"]);
const UNIQUE_TYPES = new Set(["text", "email", "phone", "url", "number"]);
const EXTERNAL_ID_TYPES = new Set(["text", "email", "number"]);
const SEARCHABLE_TYPES = new Set(["text", "textarea", "long_text", "email", "phone", "url"]);
const NOT_INDEXABLE = new Set(["long_text", "encrypted_text", "address", "multi_picklist"]);

function useCanCustomize() {
  return useAuth().can("customize_application");
}

function kindBadge(o: { is_custom: boolean; pack_key: string | null }) {
  if (o.pack_key) return <Badge tone="purple">Pack</Badge>;
  return o.is_custom ? <Badge tone="blue">Custom</Badge> : <Badge>Standard</Badge>;
}

// ================================================================ object list

export function ObjectManagerPage() {
  const canEdit = useCanCustomize();
  const [q, setQ] = useState("");
  const [creating, setCreating] = useState(false);
  const objects = useQuery({
    queryKey: ["setup", "objects"],
    queryFn: ({ signal }) => setupApi.objects(signal),
  });
  const rows = useMemo(() => {
    const term = q.trim().toLowerCase();
    return (objects.data ?? [])
      .filter((o) => !term || o.label.toLowerCase().includes(term) || o.api_name.includes(term))
      .sort((a, b) => a.label.localeCompare(b.label));
  }, [objects.data, q]);

  return (
    <div>
      <PageHeader
        title="Object Manager"
        subtitle="Standard and custom objects: fields, relationships, picklists and page layouts."
        icon={<LayersIcon size={22} className="text-brand-700" />}
        actions={
          canEdit && (
            <Button onClick={() => setCreating(true)}>
              <PlusIcon size={16} /> New Custom Object
            </Button>
          )
        }
      />
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="text-xs text-slate-600">
          {rows.length} {rows.length === 1 ? "object" : "objects"} • Sorted by Label
        </p>
        <input
          type="search"
          aria-label="Search objects"
          placeholder="Quick find…"
          className={cx(controlClass(false), "w-64")}
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>
      {objects.isPending ? (
        <Spinner label="Loading objects" />
      ) : objects.isError ? (
        <Alert tone="error">{errorMessage(objects.error)}</Alert>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-300 bg-white">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-600">
                <th className="px-4 py-2">Label</th>
                <th className="px-4 py-2">API Name</th>
                <th className="px-4 py-2">Type</th>
                <th className="px-4 py-2">Fields</th>
                <th className="px-4 py-2">Last Modified</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((o) => (
                <tr key={o.api_name} className="hover:bg-slate-50">
                  <td className="px-4 py-2">
                    <Link
                      to={`/setup/objects/${o.api_name}`}
                      className="inline-flex items-center gap-2 font-medium text-brand-700 hover:underline"
                    >
                      <ObjectIcon icon={o.icon} color={o.color} size={22} />
                      {o.label}
                    </Link>
                  </td>
                  <td className="px-4 py-2 font-mono text-xs text-slate-700">{o.api_name}</td>
                  <td className="px-4 py-2">{kindBadge(o)}</td>
                  <td className="px-4 py-2">{o.field_count}</td>
                  <td className="px-4 py-2 text-slate-600">{formatDateTimeValue(o.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {creating && <NewObjectModal onClose={() => setCreating(false)} />}
    </div>
  );
}

function NewObjectModal({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [form, setForm] = useState({
    label: "",
    plural_label: "",
    api_name: "",
    description: "",
    icon: "custom",
    color: "#6366f1",
    name_field_type: "text",
    name_label: "",
    name_format: "",
    sharing: "private",
    track_history: true,
    allow_activities: true,
    allow_notes: true,
    allow_files: true,
    searchable: true,
    allow_reports: true,
    allow_queues: false,
    show_in_portal: false,
  });
  const set = (patch: Partial<typeof form>) => setForm((f) => ({ ...f, ...patch }));
  const create = useMutation({
    mutationFn: () =>
      setupApi.createObject({
        ...form,
        api_name: form.api_name.trim() || undefined,
        plural_label: form.plural_label.trim() || undefined,
        name_label: form.name_label.trim() || undefined,
        name_format:
          form.name_field_type === "auto_number" ? form.name_format.trim() || undefined : undefined,
        description: form.description.trim() || null,
      }),
    onSuccess: (obj) => {
      void qc.invalidateQueries({ queryKey: ["setup", "objects"] });
      void qc.invalidateQueries({ queryKey: ["meta"] });
      navigate(`/setup/objects/${obj.api_name}`);
    },
  });
  const fieldErr = (k: string) => (create.error instanceof ApiError ? create.error.fields[k] : undefined);
  return (
    <Modal
      open
      onClose={onClose}
      title="New custom object"
      size="lg"
      busy={create.isPending}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => create.mutate()} loading={create.isPending} disabled={!form.label.trim()}>
            Save
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {create.isError && <Alert tone="error">{errorMessage(create.error)}</Alert>}
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Label" required error={fieldErr("label")}>
            {({ id }) => (
              <Input id={id} value={form.label} onChange={(e) => set({ label: e.target.value })} />
            )}
          </FormField>
          <FormField
            label="Plural label"
            hint="Defaults to the label + “s”."
            error={fieldErr("plural_label")}
          >
            {({ id }) => (
              <Input
                id={id}
                value={form.plural_label}
                onChange={(e) => set({ plural_label: e.target.value })}
              />
            )}
          </FormField>
          <FormField
            label="API name"
            hint="Optional. Generated from the label; ends in __c."
            error={fieldErr("api_name")}
          >
            {({ id }) => (
              <Input id={id} value={form.api_name} onChange={(e) => set({ api_name: e.target.value })} />
            )}
          </FormField>
          <FormField
            label="Sharing default"
            hint="Who sees records they don't own."
            error={fieldErr("sharing")}
          >
            {({ id }) => (
              <select
                id={id}
                className={controlClass(false)}
                value={form.sharing}
                onChange={(e) => set({ sharing: e.target.value })}
              >
                <option value="private">Private</option>
                <option value="read">Public Read Only</option>
                <option value="read_write">Public Read/Write</option>
              </select>
            )}
          </FormField>
        </div>
        <FormField label="Description">
          {({ id }) => (
            <textarea
              id={id}
              rows={2}
              className={controlClass(false)}
              value={form.description}
              onChange={(e) => set({ description: e.target.value })}
            />
          )}
        </FormField>
        <fieldset className="rounded-md border border-slate-200 p-3">
          <legend className="px-1 text-sm font-semibold text-slate-800">Record name</legend>
          <div className="grid gap-3 sm:grid-cols-3">
            <FormField label="Name field type">
              {({ id }) => (
                <select
                  id={id}
                  className={controlClass(false)}
                  value={form.name_field_type}
                  onChange={(e) => set({ name_field_type: e.target.value })}
                >
                  <option value="text">Text</option>
                  <option value="auto_number">Auto Number</option>
                </select>
              )}
            </FormField>
            <FormField label="Name field label" hint={`Defaults to “${form.label || "Object"} Name”.`}>
              {({ id }) => (
                <Input
                  id={id}
                  value={form.name_label}
                  onChange={(e) => set({ name_label: e.target.value })}
                />
              )}
            </FormField>
            {form.name_field_type === "auto_number" && (
              <FormField
                label="Display format"
                hint="e.g. REQ-{00000} or {YYYY}-{0000}"
                error={fieldErr("name_format")}
              >
                {({ id }) => (
                  <Input
                    id={id}
                    value={form.name_format}
                    onChange={(e) => set({ name_format: e.target.value })}
                  />
                )}
              </FormField>
            )}
          </div>
        </fieldset>
        <IconColorPicker
          icon={form.icon}
          color={form.color}
          onChange={(icon, color) => set({ icon, color })}
        />
        <fieldset className="grid gap-2 sm:grid-cols-2">
          <legend className="mb-1 text-sm font-semibold text-slate-800">Features</legend>
          {OBJECT_FLAGS.map((f) => (
            <Checkbox
              key={f.key}
              label={f.label}
              checked={Boolean(form[f.key as keyof typeof form])}
              onChange={(e) => set({ [f.key]: e.target.checked } as Partial<typeof form>)}
            />
          ))}
        </fieldset>
      </div>
    </Modal>
  );
}

export function IconColorPicker({
  icon,
  color,
  onChange,
  disabled,
}: {
  icon: string;
  color: string;
  onChange: (icon: string, color: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-wrap items-end gap-3">
      <FormField label="Icon">
        {({ id }) => (
          <select
            id={id}
            disabled={disabled}
            className={cx(controlClass(false), "w-48")}
            value={icon}
            onChange={(e) => onChange(e.target.value, color)}
          >
            {ICON_CHOICES.map((i) => (
              <option key={i} value={i}>
                {i}
              </option>
            ))}
          </select>
        )}
      </FormField>
      <FormField label="Colour">
        {({ id }) => (
          <input
            id={id}
            type="color"
            disabled={disabled}
            className="h-9 w-16 cursor-pointer rounded border border-slate-300 bg-white"
            value={color}
            onChange={(e) => onChange(icon, e.target.value)}
          />
        )}
      </FormField>
      <span className="pb-1">
        <ObjectIcon icon={icon} color={color} size={34} />
      </span>
    </div>
  );
}

// ================================================================ object detail

type Tab = "details" | "fields" | "layout";

export function ObjectDetailPage() {
  const { api = "" } = useParams();
  const [tab, setTab] = useState<Tab>("fields");
  const obj = useQuery({
    queryKey: ["setup", "object", api],
    queryFn: ({ signal }) => setupApi.object(api, signal),
  });
  if (obj.isPending) return <Spinner label="Loading object" />;
  if (obj.isError) return <Alert tone="error">{errorMessage(obj.error)}</Alert>;
  const o = obj.data;
  const tabs: { key: Tab; label: string }[] = [
    { key: "fields", label: "Fields & Relationships" },
    { key: "layout", label: "Page Layout" },
    { key: "details", label: "Details" },
  ];
  return (
    <div>
      <PageHeader
        breadcrumbs={[
          { label: "Setup", to: "/setup" },
          { label: "Object Manager", to: "/setup/objects" },
        ]}
        title={
          <span className="inline-flex items-center gap-3">
            {o.label} {kindBadge(o)}
          </span>
        }
        subtitle={<span className="font-mono text-xs">{o.api_name}</span>}
        icon={<ObjectIcon icon={o.icon} color={o.color} size={36} />}
        actions={
          <Link
            to={`/o/${o.api_name}`}
            className="inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:underline"
          >
            Open records <ArrowRightIcon size={14} />
          </Link>
        }
      />
      <div role="tablist" aria-label="Object sections" className="mb-4 flex gap-1 border-b border-slate-200">
        {tabs.map((t) => (
          <button
            key={t.key}
            role="tab"
            type="button"
            aria-selected={tab === t.key}
            onClick={() => setTab(t.key)}
            className={cx(
              "-mb-px border-b-2 px-4 py-2 text-sm font-medium",
              tab === t.key
                ? "border-brand-700 text-brand-700"
                : "border-transparent text-slate-600 hover:text-slate-900",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === "fields" && <FieldsTab obj={o} />}
      {/* Keys remount the forms when the saved object changes, so they never show stale values. */}
      {tab === "layout" && (
        <LayoutTab
          key={JSON.stringify([
            o.page_layout,
            o.compact_layout,
            o.list_columns,
            o.related_lists,
            o.fields.length,
          ])}
          obj={o}
        />
      )}
      {tab === "details" && <DetailsTab key={o.updated_at} obj={o} />}
    </div>
  );
}

function useObjectSaved(api: string) {
  const qc = useQueryClient();
  return (obj?: SetupObject) => {
    if (obj) qc.setQueryData(["setup", "object", api], obj);
    void qc.invalidateQueries({ queryKey: ["setup", "object", api] });
    void qc.invalidateQueries({ queryKey: ["setup", "objects"] });
    void qc.invalidateQueries({ queryKey: ["meta"] });
  };
}

// ---------------------------------------------------------------- details

function DetailsTab({ obj }: { obj: SetupObject }) {
  const canEdit = useCanCustomize();
  const toast = useToast();
  const navigate = useNavigate();
  const saved = useObjectSaved(obj.api_name);
  const initial = useMemo(
    () => ({
      label: obj.label,
      plural_label: obj.plural_label,
      description: obj.description ?? "",
      icon: obj.icon,
      color: obj.color,
      ...Object.fromEntries(OBJECT_FLAGS.map((f) => [f.key, Boolean(obj[f.key])])),
    }),
    [obj],
  );
  const [form, setForm] = useState<Record<string, string | boolean>>(initial);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const save = useMutation({
    mutationFn: () =>
      setupApi.updateObject(obj.api_name, { ...form, description: String(form.description).trim() || null }),
    onSuccess: (o) => {
      saved(o);
      toast.show("Object saved.");
    },
  });
  const remove = useMutation({
    mutationFn: () => setupApi.deleteObject(obj.api_name),
    onSuccess: () => {
      saved();
      toast.show(`${obj.label} deleted.`);
      navigate("/setup/objects");
    },
  });
  const deletable = obj.is_custom && !obj.pack_key;
  return (
    <div className="space-y-4">
      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        {save.isError && (
          <Alert tone="error" className="mb-3">
            {errorMessage(save.error)}
          </Alert>
        )}
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Label" required>
            {({ id }) => (
              <Input
                id={id}
                disabled={!canEdit}
                value={String(form.label)}
                onChange={(e) => setForm({ ...form, label: e.target.value })}
              />
            )}
          </FormField>
          <FormField label="Plural label" required>
            {({ id }) => (
              <Input
                id={id}
                disabled={!canEdit}
                value={String(form.plural_label)}
                onChange={(e) => setForm({ ...form, plural_label: e.target.value })}
              />
            )}
          </FormField>
        </div>
        <div className="mt-3">
          <FormField label="Description">
            {({ id }) => (
              <textarea
                id={id}
                rows={2}
                disabled={!canEdit}
                className={controlClass(false)}
                value={String(form.description)}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            )}
          </FormField>
        </div>
        <div className="mt-3">
          <IconColorPicker
            disabled={!canEdit}
            icon={String(form.icon)}
            color={String(form.color)}
            onChange={(icon, color) => setForm({ ...form, icon, color })}
          />
        </div>
        <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-xs text-slate-500">Record name</dt>
            <dd>
              {obj.name_label} (
              {obj.name_field_type === "auto_number" ? `Auto Number ${obj.name_format ?? ""}` : "Text"})
            </dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Detail object</dt>
            <dd>{obj.is_detail_only ? "Yes (sharing controlled by parent)" : "No"}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Industry pack</dt>
            <dd>{obj.pack_key ?? "—"}</dd>
          </div>
        </dl>
        <fieldset className="mt-4 grid gap-2 sm:grid-cols-2">
          <legend className="mb-1 text-sm font-semibold text-slate-800">Features</legend>
          {OBJECT_FLAGS.map((f) => (
            <div key={f.key}>
              <Checkbox
                label={f.label}
                disabled={!canEdit}
                checked={Boolean(form[f.key])}
                onChange={(e) => setForm({ ...form, [f.key]: e.target.checked })}
              />
              <p className="ml-6 text-xs text-slate-500">{f.hint}</p>
            </div>
          ))}
        </fieldset>
        {canEdit && (
          <div className="mt-5 flex justify-between">
            {deletable ? (
              <Button variant="danger" onClick={() => setConfirmDelete(true)}>
                <TrashIcon size={16} /> Delete object
              </Button>
            ) : (
              <span />
            )}
            <Button onClick={() => save.mutate()} loading={save.isPending}>
              Save
            </Button>
          </div>
        )}
      </section>
      <ConfirmDialog
        open={confirmDelete}
        title={`Delete ${obj.label}?`}
        confirmLabel="Delete object"
        tone="danger"
        loading={remove.isPending}
        onCancel={() => setConfirmDelete(false)}
        onConfirm={() => remove.mutate()}
      >
        {remove.isError && (
          <Alert tone="error" className="mb-2">
            {errorMessage(remove.error)}
          </Alert>
        )}
        The object, its fields, list views and permissions are removed. Objects that still have records can't
        be deleted.
      </ConfirmDialog>
    </div>
  );
}

// ---------------------------------------------------------------- fields

function fieldKind(f: FieldDescribe) {
  if (f.is_system) return <Badge>System</Badge>;
  if (f.is_custom) return <Badge tone="blue">Custom</Badge>;
  return <Badge>Standard</Badge>;
}

function FieldsTab({ obj }: { obj: SetupObject }) {
  const canEdit = useCanCustomize();
  const toast = useToast();
  const saved = useObjectSaved(obj.api_name);
  const [q, setQ] = useState("");
  const [editing, setEditing] = useState<FieldDescribe | "new" | null>(null);
  const [deleting, setDeleting] = useState<FieldDescribe | null>(null);
  const remove = useMutation({
    mutationFn: (f: FieldDescribe) => setupApi.deleteField(obj.api_name, f.api_name),
    onSuccess: (o, f) => {
      saved(o);
      setDeleting(null);
      toast.show(`${f.label} moved to deleted fields.`);
    },
  });
  const restore = useMutation({
    mutationFn: (api: string) => setupApi.restoreField(obj.api_name, api),
    onSuccess: (o) => {
      saved(o);
      toast.show("Field restored.");
    },
  });
  const fields = useMemo(() => {
    const term = q.trim().toLowerCase();
    return obj.fields
      .filter((f) => !term || f.label.toLowerCase().includes(term) || f.api_name.includes(term))
      .sort((a, b) => a.label.localeCompare(b.label));
  }, [obj.fields, q]);
  const target = (f: FieldDescribe) =>
    f.options.target
      ? ` (${f.options.target})`
      : f.options.targets
        ? ` (${f.options.targets.join(", ")})`
        : "";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-slate-600">
          {fields.length} fields • Sorted by Field Label • Custom fields are hidden from every profile except
          System Administrator until you grant access in{" "}
          <Link to="/setup/profiles" className="text-brand-700 hover:underline">
            Profiles
          </Link>
          .
        </p>
        <div className="flex items-center gap-2">
          <input
            type="search"
            aria-label="Search fields"
            placeholder="Quick find…"
            className={cx(controlClass(false), "w-56")}
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          {canEdit && (
            <Button onClick={() => setEditing("new")}>
              <PlusIcon size={16} /> New Field
            </Button>
          )}
        </div>
      </div>
      <div className="overflow-x-auto rounded-lg border border-slate-300 bg-white">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs text-slate-600">
              <th className="px-4 py-2">Field Label</th>
              <th className="px-4 py-2">API Name</th>
              <th className="px-4 py-2">Data Type</th>
              <th className="px-4 py-2">Attributes</th>
              <th className="px-4 py-2">Kind</th>
              <th className="px-4 py-2">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {fields.map((f) => (
              <tr key={f.api_name} className="hover:bg-slate-50">
                <td className="px-4 py-2 font-medium text-slate-900">{f.label}</td>
                <td className="px-4 py-2 font-mono text-xs text-slate-700">{f.api_name}</td>
                <td className="px-4 py-2">
                  {FIELD_TYPE_LABELS[f.type] ?? f.type}
                  <span className="text-slate-500">{target(f)}</span>
                </td>
                <td className="px-4 py-2 text-xs text-slate-600">
                  {[
                    f.required && "Required",
                    f.is_unique && "Unique",
                    f.external_id && "External ID",
                    f.indexed && "Indexed",
                    f.track_history && "History",
                    f.options.is_path && "Path",
                  ]
                    .filter(Boolean)
                    .join(" • ")}
                </td>
                <td className="px-4 py-2">{fieldKind(f)}</td>
                <td className="whitespace-nowrap px-4 py-2 text-right">
                  {canEdit && !f.is_system && (
                    <button
                      type="button"
                      className="text-sm font-medium text-brand-700 hover:underline"
                      onClick={() => setEditing(f)}
                    >
                      Edit
                    </button>
                  )}
                  {canEdit && f.is_custom && !obj.pack_key && (
                    <button
                      type="button"
                      className="ml-3 text-sm font-medium text-red-700 hover:underline"
                      onClick={() => setDeleting(f)}
                    >
                      Delete
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {obj.deleted_fields.length > 0 && (
        <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="font-semibold text-slate-900">Deleted fields</h3>
          <p className="text-xs text-slate-600">
            Deleted fields keep their data until they are purged (see Data Retention settings).
          </p>
          <ul className="mt-2 divide-y divide-slate-100 text-sm">
            {obj.deleted_fields.map((f) => (
              <li key={f.api_name} className="flex items-center justify-between py-2">
                <span>
                  {f.label} <span className="font-mono text-xs text-slate-500">{f.api_name}</span>{" "}
                  <span className="text-xs text-slate-500">deleted {formatDateTimeValue(f.deleted_at)}</span>
                </span>
                {canEdit && (
                  <Button
                    size="sm"
                    variant="secondary"
                    loading={restore.isPending && restore.variables === f.api_name}
                    onClick={() => restore.mutate(f.api_name)}
                  >
                    Restore
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
      {editing && (
        <FieldModal obj={obj} field={editing === "new" ? null : editing} onClose={() => setEditing(null)} />
      )}
      <ConfirmDialog
        open={deleting !== null}
        title={`Delete field ${deleting?.label ?? ""}?`}
        confirmLabel="Delete field"
        tone="danger"
        loading={remove.isPending}
        onCancel={() => setDeleting(null)}
        onConfirm={() => deleting && remove.mutate(deleting)}
      >
        {remove.isError && (
          <Alert tone="error" className="mb-2">
            {errorMessage(remove.error)}
          </Alert>
        )}
        The field disappears from layouts, list views and reports. You can restore it from Deleted fields
        until it is purged.
      </ConfirmDialog>
    </div>
  );
}

type PicklistRow = { value: string; label: string; active: boolean; default: boolean; color: string };

function toRows(values: PicklistValue[] | undefined): PicklistRow[] {
  return (values ?? []).map((v) => ({
    value: v.value,
    label: v.label,
    active: v.active,
    default: Boolean(v.default),
    color: v.color ?? "",
  }));
}

export function FieldModal({
  obj,
  field,
  onClose,
}: {
  obj: SetupObject;
  field: FieldDescribe | null;
  onClose: () => void;
}) {
  const saved = useObjectSaved(obj.api_name);
  const toast = useToast();
  const creating = field === null;
  const objects = useQuery({
    queryKey: ["setup", "objects"],
    queryFn: ({ signal }) => setupApi.objects(signal),
  });
  const types = obj.field_types.filter((t) => t !== "auto_number");
  const [type, setType] = useState<string>(field?.type ?? "text");
  const [form, setForm] = useState({
    label: field?.label ?? "",
    api_name: "",
    help_text: field?.help_text ?? "",
    required: field?.required ?? false,
    is_unique: field?.is_unique ?? false,
    external_id: field?.external_id ?? false,
    indexed: field?.indexed ?? false,
    searchable: field?.searchable ?? false,
    track_history: field?.track_history ?? false,
    default_access: field?.default_access ?? "hidden",
    default_value:
      field?.default_value === null || field?.default_value === undefined ? "" : String(field.default_value),
  });
  const [maxLength, setMaxLength] = useState(
    field?.options.max_length ? String(field.options.max_length) : "",
  );
  const [scale, setScale] = useState(field?.options.scale !== undefined ? String(field.options.scale) : "");
  const [min, setMin] = useState(field?.options.min !== undefined ? String(field.options.min) : "");
  const [max, setMax] = useState(field?.options.max !== undefined ? String(field.options.max) : "");
  const [target, setTarget] = useState(field?.options.target ?? "");
  const [deleteRule, setDeleteRule] = useState(field?.options.delete_rule ?? "clear");
  const [isPath, setIsPath] = useState(Boolean(field?.options.is_path));
  const [values, setValues] = useState<PicklistRow[]>(toRows(field?.options.values));
  const [newValues, setNewValues] = useState("");
  const set = (patch: Partial<typeof form>) => setForm((f) => ({ ...f, ...patch }));
  const managedTargets = Boolean(field?.options.targets);

  const options = (): Record<string, unknown> | undefined => {
    const o: Record<string, unknown> = {};
    if (LENGTH_TYPES.has(type) && maxLength.trim()) o.max_length = Number(maxLength);
    if (NUMERIC_TYPES.has(type)) {
      if (scale.trim()) o.scale = Number(scale);
      if (min.trim()) o.min = Number(min);
      if (max.trim()) o.max = Number(max);
    }
    if (type === "picklist" || type === "multi_picklist") {
      o.values = values.map((v) => ({
        value: v.value,
        label: v.label || v.value,
        active: v.active,
        ...(v.default ? { default: true } : {}),
        ...(v.color ? { color: v.color } : {}),
      }));
      if (type === "picklist") o.is_path = isPath;
    }
    if ((type === "lookup" || type === "master_detail") && !managedTargets) {
      o.target = target;
      if (type === "lookup") o.delete_rule = deleteRule;
    }
    return Object.keys(o).length ? o : undefined;
  };

  const defaultValue = (): unknown => {
    const raw = form.default_value.trim();
    if (raw === "") return null;
    if (type === "checkbox") return raw === "true";
    if (NUMERIC_TYPES.has(type)) return Number(raw);
    return raw;
  };

  const save = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = {
        label: form.label,
        help_text: form.help_text.trim() || null,
        required: form.required,
        is_unique: form.is_unique,
        indexed: form.indexed,
        searchable: form.searchable,
        track_history: form.track_history,
        default_access: form.default_access,
        default_value: defaultValue(),
        options: options(),
      };
      if (creating) {
        body.type = type;
        body.api_name = form.api_name.trim() || undefined;
        body.external_id = form.external_id;
        return setupApi.createField(obj.api_name, body);
      }
      return setupApi.updateField(obj.api_name, field.api_name, body);
    },
    onSuccess: (o) => {
      saved(o);
      toast.show(creating ? "Field created." : "Field saved.");
      onClose();
    },
  });
  const err = (k: string) => (save.error instanceof ApiError ? save.error.fields[k] : undefined);

  const addValues = () => {
    // Picklist values are unique ignoring case (as on the server), including within the pasted batch.
    const seen = new Set(values.map((v) => v.value.toLowerCase()));
    const added: string[] = [];
    for (const raw of newValues.split("\n")) {
      const v = raw.trim();
      if (!v || seen.has(v.toLowerCase())) continue;
      seen.add(v.toLowerCase());
      added.push(v);
    }
    setValues([
      ...values,
      ...added.map((v) => ({ value: v, label: v, active: true, default: false, color: "" })),
    ]);
    setNewValues("");
  };
  const move = (i: number, d: -1 | 1) => {
    const j = i + d;
    if (j < 0 || j >= values.length) return;
    const next = [...values];
    [next[i], next[j]] = [next[j]!, next[i]!];
    setValues(next);
  };

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      busy={save.isPending}
      title={creating ? `New field on ${obj.label}` : `Edit ${field.label}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => save.mutate()} loading={save.isPending} disabled={!form.label.trim()}>
            Save
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {save.isError && <Alert tone="error">{errorMessage(save.error)}</Alert>}
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Data type" error={err("type")}>
            {({ id }) => (
              <select
                id={id}
                className={controlClass(false)}
                value={type}
                disabled={!creating}
                onChange={(e) => setType(e.target.value)}
              >
                {(creating ? types : [type]).map((t) => (
                  <option key={t} value={t}>
                    {FIELD_TYPE_LABELS[t] ?? t}
                  </option>
                ))}
              </select>
            )}
          </FormField>
          <FormField label="Field label" required error={err("label")}>
            {({ id }) => (
              <Input id={id} value={form.label} onChange={(e) => set({ label: e.target.value })} />
            )}
          </FormField>
          {creating ? (
            <FormField
              label="API name"
              hint="Optional. Generated from the label; ends in __c."
              error={err("api_name")}
            >
              {({ id }) => (
                <Input id={id} value={form.api_name} onChange={(e) => set({ api_name: e.target.value })} />
              )}
            </FormField>
          ) : (
            <div>
              <p className="text-sm font-medium text-slate-700">API name</p>
              <p className="mt-1 font-mono text-sm">{field.api_name}</p>
            </div>
          )}
          <FormField
            label="Default access"
            hint="For profiles without a field-level security override."
            error={err("default_access")}
          >
            {({ id }) => (
              <select
                id={id}
                className={controlClass(false)}
                value={form.default_access}
                onChange={(e) => set({ default_access: e.target.value as "hidden" | "read" | "edit" })}
              >
                <option value="hidden">Hidden (secure default)</option>
                <option value="read">Read only</option>
                <option value="edit">Editable</option>
              </select>
            )}
          </FormField>
        </div>
        <FormField label="Help text" hint="Shown as a tooltip on record pages.">
          {({ id }) => (
            <textarea
              id={id}
              rows={2}
              className={controlClass(false)}
              value={form.help_text}
              onChange={(e) => set({ help_text: e.target.value })}
            />
          )}
        </FormField>

        {LENGTH_TYPES.has(type) && (
          <FormField label="Maximum length" error={err("options.max_length")}>
            {({ id }) => (
              <Input
                id={id}
                type="number"
                min={1}
                className="w-40"
                value={maxLength}
                onChange={(e) => setMaxLength(e.target.value)}
              />
            )}
          </FormField>
        )}
        {NUMERIC_TYPES.has(type) && (
          <div className="grid gap-3 sm:grid-cols-3">
            <FormField label="Decimal places" error={err("options.scale")}>
              {({ id }) => (
                <Input
                  id={id}
                  type="number"
                  min={0}
                  max={6}
                  value={scale}
                  onChange={(e) => setScale(e.target.value)}
                />
              )}
            </FormField>
            <FormField label="Minimum" error={err("options.min")}>
              {({ id }) => (
                <Input id={id} type="number" value={min} onChange={(e) => setMin(e.target.value)} />
              )}
            </FormField>
            <FormField label="Maximum" error={err("options.max")}>
              {({ id }) => (
                <Input id={id} type="number" value={max} onChange={(e) => setMax(e.target.value)} />
              )}
            </FormField>
          </div>
        )}
        {(type === "lookup" || type === "master_detail") && (
          <div className="grid gap-3 sm:grid-cols-2">
            <FormField label="Related to" required error={err("options.target")}>
              {({ id }) =>
                managedTargets ? (
                  <p id={id} className="mt-1 text-sm">
                    {field?.options.targets?.join(", ")}
                  </p>
                ) : (
                  <select
                    id={id}
                    className={controlClass(Boolean(err("options.target")))}
                    value={target}
                    disabled={!creating}
                    onChange={(e) => setTarget(e.target.value)}
                  >
                    <option value="">Choose an object…</option>
                    {(objects.data ?? [])
                      .filter((o: SetupObjectSummary) => type === "lookup" || o.api_name !== obj.api_name)
                      .sort((a, b) => a.label.localeCompare(b.label))
                      .map((o) => (
                        <option key={o.api_name} value={o.api_name}>
                          {o.label}
                        </option>
                      ))}
                  </select>
                )
              }
            </FormField>
            {type === "lookup" && !managedTargets && (
              <FormField label="When the related record is deleted" error={err("options.delete_rule")}>
                {({ id }) => (
                  <select
                    id={id}
                    className={controlClass(false)}
                    value={deleteRule}
                    onChange={(e) => setDeleteRule(e.target.value)}
                  >
                    <option value="clear">Clear this field</option>
                    <option value="restrict">Don't allow the deletion</option>
                  </select>
                )}
              </FormField>
            )}
            {type === "master_detail" && (
              <p className="text-xs text-slate-600 sm:col-span-2">
                Master-detail: the record is required, inherits sharing from its parent and is deleted with
                it. Only allowed on objects without records.
              </p>
            )}
          </div>
        )}
        {(type === "picklist" || type === "multi_picklist") && (
          <fieldset className="rounded-md border border-slate-200 p-3">
            <legend className="px-1 text-sm font-semibold text-slate-800">Values</legend>
            {err("options.values") && <p className="mb-2 text-sm text-red-700">{err("options.values")}</p>}
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-600">
                  <th className="py-1">Value</th>
                  <th className="py-1">Label</th>
                  <th className="py-1">Colour</th>
                  <th className="py-1">Active</th>
                  <th className="py-1">Default</th>
                  <th className="py-1">
                    <span className="sr-only">Order</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {values.map((v, i) => (
                  <tr key={`${v.value}-${i}`}>
                    <td className="py-1 pr-2 font-mono text-xs">{v.value}</td>
                    <td className="py-1 pr-2">
                      <Input
                        aria-label={`Label for ${v.value}`}
                        value={v.label}
                        onChange={(e) =>
                          setValues(values.map((x, k) => (k === i ? { ...x, label: e.target.value } : x)))
                        }
                      />
                    </td>
                    <td className="py-1 pr-2">
                      <input
                        type="color"
                        aria-label={`Colour for ${v.value}`}
                        className="h-8 w-10 rounded border border-slate-300"
                        value={v.color || "#94a3b8"}
                        onChange={(e) =>
                          setValues(values.map((x, k) => (k === i ? { ...x, color: e.target.value } : x)))
                        }
                      />
                    </td>
                    <td className="py-1">
                      <input
                        type="checkbox"
                        aria-label={`${v.value} active`}
                        checked={v.active}
                        onChange={(e) =>
                          setValues(values.map((x, k) => (k === i ? { ...x, active: e.target.checked } : x)))
                        }
                      />
                    </td>
                    <td className="py-1">
                      <input
                        type="radio"
                        name="default"
                        aria-label={`${v.value} default`}
                        checked={v.default}
                        onChange={() => setValues(values.map((x, k) => ({ ...x, default: k === i })))}
                      />
                    </td>
                    <td className="whitespace-nowrap py-1 text-right">
                      <button
                        type="button"
                        className="px-1 text-slate-600 hover:text-slate-900"
                        aria-label={`Move ${v.value} up`}
                        onClick={() => move(i, -1)}
                      >
                        ↑
                      </button>
                      <button
                        type="button"
                        className="px-1 text-slate-600 hover:text-slate-900"
                        aria-label={`Move ${v.value} down`}
                        onClick={() => move(i, 1)}
                      >
                        ↓
                      </button>
                      {!field?.options.values?.some((ov) => ov.value === v.value) && (
                        <button
                          type="button"
                          className="px-1 text-red-700"
                          aria-label={`Remove ${v.value}`}
                          onClick={() => setValues(values.filter((_, k) => k !== i))}
                        >
                          ×
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-1 text-xs text-slate-500">
              Saved values can be deactivated but not removed, so existing records keep their value.
            </p>
            <div className="mt-2 flex items-end gap-2">
              <FormField label="Add values" hint="One per line.">
                {({ id }) => (
                  <textarea
                    id={id}
                    rows={2}
                    className={cx(controlClass(false), "w-72")}
                    value={newValues}
                    onChange={(e) => setNewValues(e.target.value)}
                  />
                )}
              </FormField>
              <Button variant="secondary" onClick={addValues} disabled={!newValues.trim()}>
                Add
              </Button>
            </div>
            {type === "picklist" && (
              <div className="mt-3">
                <Checkbox
                  label="Show as a path (stage chevrons) on record pages"
                  checked={isPath}
                  onChange={(e) => setIsPath(e.target.checked)}
                />
              </div>
            )}
          </fieldset>
        )}

        <fieldset className="grid gap-2 sm:grid-cols-2">
          <legend className="mb-1 text-sm font-semibold text-slate-800">Attributes</legend>
          <Checkbox
            label="Required"
            checked={form.required || type === "master_detail"}
            disabled={type === "master_detail"}
            onChange={(e) => set({ required: e.target.checked })}
          />
          {UNIQUE_TYPES.has(type) && (
            <Checkbox
              label="Unique"
              checked={form.is_unique}
              onChange={(e) => set({ is_unique: e.target.checked })}
            />
          )}
          {creating && EXTERNAL_ID_TYPES.has(type) && (
            <Checkbox
              label="External ID (used to match rows on import)"
              checked={form.external_id}
              onChange={(e) => set({ external_id: e.target.checked })}
            />
          )}
          {!NOT_INDEXABLE.has(type) && (
            <Checkbox
              label="Filterable & sortable at scale (indexed)"
              checked={form.indexed}
              onChange={(e) => set({ indexed: e.target.checked })}
            />
          )}
          {SEARCHABLE_TYPES.has(type) && (
            <Checkbox
              label="Include in global search"
              checked={form.searchable}
              onChange={(e) => set({ searchable: e.target.checked })}
            />
          )}
          {type !== "encrypted_text" && (
            <Checkbox
              label="Track history"
              checked={form.track_history}
              onChange={(e) => set({ track_history: e.target.checked })}
            />
          )}
        </fieldset>
        {![
          "lookup",
          "master_detail",
          "address",
          "multi_picklist",
          "picklist",
          "user",
          "encrypted_text",
          "long_text",
        ].includes(type) && (
          <FormField
            label="Default value"
            hint={type === "checkbox" ? "true or false" : "Used when a new record leaves the field empty."}
            error={err("default_value")}
          >
            {({ id }) =>
              type === "checkbox" ? (
                <select
                  id={id}
                  className={cx(controlClass(false), "w-40")}
                  value={form.default_value || "false"}
                  onChange={(e) => set({ default_value: e.target.value })}
                >
                  <option value="false">Unchecked</option>
                  <option value="true">Checked</option>
                </select>
              ) : (
                <Input
                  id={id}
                  value={form.default_value}
                  onChange={(e) => set({ default_value: e.target.value })}
                />
              )
            }
          </FormField>
        )}
      </div>
    </Modal>
  );
}

// ---------------------------------------------------------------- layout

function OrderedList({
  items,
  labels,
  onChange,
  disabled,
  available,
  addLabel,
}: {
  items: string[];
  labels: Record<string, string>;
  onChange: (items: string[]) => void;
  disabled?: boolean;
  available: string[];
  addLabel: string;
}) {
  const [adding, setAdding] = useState("");
  const move = (i: number, d: -1 | 1) => {
    const j = i + d;
    if (j < 0 || j >= items.length) return;
    const next = [...items];
    [next[i], next[j]] = [next[j]!, next[i]!];
    onChange(next);
  };
  return (
    <div>
      <ol className="divide-y divide-slate-100 rounded-md border border-slate-200">
        {items.map((f, i) => (
          <li key={f} className="flex items-center justify-between px-3 py-1.5 text-sm">
            <span>
              {labels[f] ?? f} <span className="font-mono text-xs text-slate-400">{f}</span>
            </span>
            {!disabled && (
              <span className="whitespace-nowrap">
                <button
                  type="button"
                  className="px-1 text-slate-600 hover:text-slate-900"
                  aria-label={`Move ${labels[f] ?? f} up`}
                  onClick={() => move(i, -1)}
                >
                  ↑
                </button>
                <button
                  type="button"
                  className="px-1 text-slate-600 hover:text-slate-900"
                  aria-label={`Move ${labels[f] ?? f} down`}
                  onClick={() => move(i, 1)}
                >
                  ↓
                </button>
                <button
                  type="button"
                  className="px-1 text-red-700"
                  aria-label={`Remove ${labels[f] ?? f}`}
                  onClick={() => onChange(items.filter((x) => x !== f))}
                >
                  ×
                </button>
              </span>
            )}
          </li>
        ))}
        {items.length === 0 && <li className="px-3 py-2 text-sm text-slate-500">Empty</li>}
      </ol>
      {!disabled && available.length > 0 && (
        <div className="mt-2 flex gap-2">
          <select
            aria-label={addLabel}
            className={cx(controlClass(false), "max-w-xs")}
            value={adding}
            onChange={(e) => setAdding(e.target.value)}
          >
            <option value="">{addLabel}…</option>
            {available.map((f) => (
              <option key={f} value={f}>
                {labels[f] ?? f}
              </option>
            ))}
          </select>
          <Button
            size="sm"
            variant="secondary"
            disabled={!adding}
            onClick={() => {
              onChange([...items, adding]);
              setAdding("");
            }}
          >
            Add
          </Button>
        </div>
      )}
    </div>
  );
}

function LayoutTab({ obj }: { obj: SetupObject }) {
  const canEdit = useCanCustomize();
  const toast = useToast();
  const saved = useObjectSaved(obj.api_name);
  const labels = useMemo(
    () => Object.fromEntries(obj.fields.map((f) => [f.api_name, f.label])),
    [obj.fields],
  );
  const [sections, setSections] = useState<LayoutSection[]>(obj.page_layout);
  const [compact, setCompact] = useState<string[]>(obj.compact_layout);
  const [columns, setColumns] = useState<string[]>(obj.list_columns);
  const [related, setRelated] = useState(obj.related_lists);
  const placed = new Set(sections.flatMap((s) => s.fields));
  const allFields = obj.fields.map((f) => f.api_name);
  const unplaced = allFields.filter((f) => !placed.has(f));
  const save = useMutation({
    mutationFn: () =>
      setupApi.updateObject(obj.api_name, {
        page_layout: sections,
        compact_layout: compact,
        list_columns: columns,
        related_lists: related,
      }),
    onSuccess: (o) => {
      saved(o);
      toast.show("Layout saved.");
    },
  });
  const updateSection = (i: number, patch: Partial<LayoutSection>) =>
    setSections(sections.map((s, k) => (k === i ? { ...s, ...patch } : s)));
  const moveSection = (i: number, d: -1 | 1) => {
    const j = i + d;
    if (j < 0 || j >= sections.length) return;
    const next = [...sections];
    [next[i], next[j]] = [next[j]!, next[i]!];
    setSections(next);
  };
  const moveRelated = (i: number, d: -1 | 1) => {
    const j = i + d;
    if (j < 0 || j >= related.length) return;
    const next = [...related];
    [next[i], next[j]] = [next[j]!, next[i]!];
    setRelated(next);
  };

  return (
    <div className="space-y-4">
      {save.isError && <Alert tone="error">{errorMessage(save.error)}</Alert>}
      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-slate-900">Record page sections</h3>
            <p className="text-xs text-slate-600">
              Order of sections and fields on the Details tab.{" "}
              {unplaced.length > 0 && `${unplaced.length} field(s) not on the layout.`}
            </p>
          </div>
          {canEdit && (
            <Button
              size="sm"
              variant="secondary"
              onClick={() => setSections([...sections, { label: "New Section", columns: 2, fields: [] }])}
            >
              <PlusIcon size={14} /> Add section
            </Button>
          )}
        </div>
        <div className="space-y-4">
          {sections.map((s, i) => (
            <div key={i} className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <Input
                  aria-label={`Section ${i + 1} name`}
                  disabled={!canEdit}
                  className="max-w-xs"
                  value={s.label}
                  onChange={(e) => updateSection(i, { label: e.target.value })}
                />
                <select
                  aria-label={`Section ${i + 1} columns`}
                  disabled={!canEdit}
                  className={cx(controlClass(false), "w-32")}
                  value={s.columns}
                  onChange={(e) => updateSection(i, { columns: Number(e.target.value) as 1 | 2 })}
                >
                  <option value={1}>1 column</option>
                  <option value={2}>2 columns</option>
                </select>
                {canEdit && (
                  <span className="ml-auto whitespace-nowrap">
                    <button
                      type="button"
                      className="px-1 text-slate-600"
                      aria-label={`Move section ${s.label} up`}
                      onClick={() => moveSection(i, -1)}
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      className="px-1 text-slate-600"
                      aria-label={`Move section ${s.label} down`}
                      onClick={() => moveSection(i, 1)}
                    >
                      ↓
                    </button>
                    <button
                      type="button"
                      className="px-1 text-red-700"
                      aria-label={`Remove section ${s.label}`}
                      onClick={() => setSections(sections.filter((_, k) => k !== i))}
                    >
                      ×
                    </button>
                  </span>
                )}
              </div>
              <OrderedList
                items={s.fields}
                labels={labels}
                disabled={!canEdit}
                available={unplaced}
                addLabel="Add field"
                onChange={(fields) => updateSection(i, { fields })}
              />
            </div>
          ))}
        </div>
      </section>
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="font-semibold text-slate-900">Highlights panel</h3>
          <p className="mb-2 text-xs text-slate-600">
            Key fields shown under the record name (compact layout).
          </p>
          <OrderedList
            items={compact}
            labels={labels}
            disabled={!canEdit}
            available={allFields.filter((f) => !compact.includes(f))}
            addLabel="Add field"
            onChange={setCompact}
          />
        </section>
        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="font-semibold text-slate-900">Default list columns</h3>
          <p className="mb-2 text-xs text-slate-600">Columns of new list views and search results.</p>
          <OrderedList
            items={columns}
            labels={labels}
            disabled={!canEdit}
            available={allFields.filter((f) => !columns.includes(f))}
            addLabel="Add column"
            onChange={setColumns}
          />
        </section>
      </div>
      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="font-semibold text-slate-900">Related lists</h3>
        <p className="mb-2 text-xs text-slate-600">
          Shown on the Related tab. Lookup fields on other objects pointing here can appear as related lists.
        </p>
        <ol className="divide-y divide-slate-100 rounded-md border border-slate-200">
          {related.map((r, i) => (
            <li
              key={`${r.object}.${r.field}`}
              className="flex flex-wrap items-center gap-2 px-3 py-1.5 text-sm"
            >
              <Input
                aria-label={`Label for related list ${r.label}`}
                disabled={!canEdit}
                className="max-w-xs"
                value={r.label}
                onChange={(e) =>
                  setRelated(related.map((x, k) => (k === i ? { ...x, label: e.target.value } : x)))
                }
              />
              <span className="font-mono text-xs text-slate-500">
                {r.object}.{r.field}
              </span>
              {canEdit && (
                <span className="ml-auto whitespace-nowrap">
                  <button
                    type="button"
                    className="px-1 text-slate-600"
                    aria-label={`Move ${r.label} up`}
                    onClick={() => moveRelated(i, -1)}
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    className="px-1 text-slate-600"
                    aria-label={`Move ${r.label} down`}
                    onClick={() => moveRelated(i, 1)}
                  >
                    ↓
                  </button>
                  <button
                    type="button"
                    className="px-1 text-red-700"
                    aria-label={`Remove ${r.label}`}
                    onClick={() => setRelated(related.filter((_, k) => k !== i))}
                  >
                    ×
                  </button>
                </span>
              )}
            </li>
          ))}
          {related.length === 0 && <li className="px-3 py-2 text-sm text-slate-500">No related lists</li>}
        </ol>
      </section>
      {canEdit && (
        <div className="flex justify-end gap-2">
          <Button
            variant="secondary"
            onClick={() => {
              setSections(obj.page_layout);
              setCompact(obj.compact_layout);
              setColumns(obj.list_columns);
              setRelated(obj.related_lists);
            }}
          >
            Reset
          </Button>
          <Button onClick={() => save.mutate()} loading={save.isPending}>
            Save layout
          </Button>
        </div>
      )}
    </div>
  );
}

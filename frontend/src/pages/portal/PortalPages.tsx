// Customer portal: home, record lists, record detail with comments/files/actions, new case.
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { API_BASE, errorMessage } from "../../api/client";
import { portalApi, type PortalDescribe, type PortalRecord } from "../../api/portal";
import { fileUrl, uploadFile } from "../../api/records";
import type { RecordData } from "../../api/types";
import { useAuth } from "../../auth/context";
import { DownloadIcon, PaperclipIcon, PlusIcon, SearchIcon, UploadIcon } from "../../components/icons";
import { FieldDisplay, PicklistPill } from "../../components/record/FieldDisplay";
import { controlClass } from "../../components/record/FieldInput";
import { ObjectIcon } from "../../components/record/ObjectIcon";
import {
  Alert,
  Button,
  Checkbox,
  EmptyState,
  FormField,
  Input,
  Spinner,
  useToast,
} from "../../components/ui";
import { cx } from "../../components/ui/cx";
import { Modal } from "../../components/ui/Modal";
import { formatDateTimeValue } from "../../lib/records";

const PDF_OBJECTS = new Set(["invoice", "quote"]);

function usePortalMe() {
  return useQuery({ queryKey: ["portal", "me"], queryFn: ({ signal }) => portalApi.me(signal) });
}

function useDescribe(object: string) {
  return useQuery({
    queryKey: ["portal", "describe", object],
    queryFn: ({ signal }) => portalApi.describe(object, signal),
    enabled: Boolean(object),
    staleTime: 5 * 60_000,
  });
}

function label(meta: PortalDescribe, api: string) {
  if (api === "name") return meta.name_label;
  if (api === "created_at") return "Created";
  if (api === "updated_at") return "Last updated";
  return meta.fields[api]?.label ?? api;
}

function Value({ meta, record, api }: { meta: PortalDescribe; record: RecordData; api: string }) {
  const field = meta.fields[api];
  if (field?.type === "picklist") return <PicklistPill field={field} value={record.fields[api]} />;
  return <FieldDisplay field={field} record={record} apiName={api} linkBase="/portal" />;
}

// ================================================================ home

export function PortalHomePage() {
  const { me: auth } = useAuth();
  const me = usePortalMe();
  if (me.isPending) return <Spinner label="Loading" />;
  if (me.isError) return <Alert tone="error">{errorMessage(me.error)}</Alert>;
  const firstName = auth?.user.name.split(" ")[0] ?? "";
  const canCreateCase = me.data.objects.some((o) => o.api_name === "case" && o.can_create);
  return (
    <div className="space-y-6">
      <div className="rounded-lg bg-gradient-to-r from-brand-50 to-indigo-50 px-6 py-5">
        <h1 className="text-2xl font-semibold text-slate-900">Hello, {firstName}</h1>
        <p className="mt-1 text-sm text-slate-600">
          {me.data.account ? `${me.data.account.name} · ` : ""}
          Follow your requests, documents and invoices in one place.
        </p>
        {canCreateCase && (
          <Link
            to="/portal/cases/new"
            className="mt-3 inline-flex items-center gap-1 rounded-full bg-brand-700 px-4 py-1.5 text-sm font-semibold text-white hover:bg-brand-800"
          >
            <PlusIcon size={14} /> Get help
          </Link>
        )}
      </div>
      {me.data.objects.length === 0 ? (
        <EmptyState
          title="Nothing to show yet"
          description="When we share records with you, they appear here."
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {me.data.objects.map((o) => (
            <Link
              key={o.api_name}
              to={`/portal/o/${o.api_name}`}
              className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm hover:border-brand-300 hover:shadow"
            >
              <ObjectIcon icon={o.icon} color="#0176d3" size={36} />
              <span>
                <span className="block font-semibold text-slate-900">{o.plural_label}</span>
                {me.data.counts[o.api_name] !== undefined && (
                  <span className="text-sm text-slate-600">{me.data.counts[o.api_name]} total</span>
                )}
              </span>
            </Link>
          ))}
        </div>
      )}
      {me.data.contact && (
        <section className="rounded-lg border border-slate-200 bg-white p-4 text-sm shadow-sm">
          <h2 className="font-semibold text-slate-900">Your details</h2>
          <p className="mt-1 text-slate-700">
            {me.data.contact.name}
            {me.data.contact.email && ` · ${me.data.contact.email}`}
            {me.data.contact.phone && ` · ${me.data.contact.phone}`}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            To change these details, contact us or reply on one of your requests.
          </p>
        </section>
      )}
    </div>
  );
}

// ================================================================ list

export function PortalListPage() {
  const { object = "" } = useParams();
  const me = usePortalMe();
  const meta = useDescribe(object);
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const list = useInfiniteQuery({
    queryKey: ["portal", "list", object, search],
    queryFn: ({ pageParam, signal }) => portalApi.list(object, search || undefined, pageParam, signal),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });
  if (meta.isPending) return <Spinner label="Loading" />;
  if (meta.isError) return <Alert tone="error">{errorMessage(meta.error)}</Alert>;
  const m = meta.data;
  const columns = m.list_columns.includes("name") ? m.list_columns : ["name", ...m.list_columns];
  const canCreate = object === "case" && me.data?.objects.some((o) => o.api_name === "case" && o.can_create);
  const items = list.data?.pages.flatMap((p) => p.items) ?? [];
  const onSearch = (e: FormEvent) => {
    e.preventDefault();
    setSearch(q.trim());
  };
  return (
    <div className="space-y-4">
      <nav aria-label="Breadcrumb" className="text-xs text-slate-500">
        <Link to="/portal" className="hover:underline">
          Home
        </Link>{" "}
        / {m.plural_label}
      </nav>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="flex items-center gap-2 text-2xl font-semibold text-slate-900">
          <ObjectIcon icon={m.icon} color={m.color} size={30} /> {m.plural_label}
        </h1>
        <div className="flex items-center gap-2">
          <form onSubmit={onSearch} role="search" className="relative">
            <SearchIcon
              size={14}
              className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400"
            />
            <input
              aria-label={`Search ${m.plural_label}`}
              type="search"
              placeholder="Search…"
              className={cx(controlClass(false), "w-56 pl-8")}
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </form>
          {canCreate && (
            <Link
              to="/portal/cases/new"
              className="inline-flex items-center gap-1 rounded-md bg-brand-700 px-3 py-2 text-sm font-semibold text-white hover:bg-brand-800"
            >
              <PlusIcon size={14} /> New case
            </Link>
          )}
        </div>
      </div>
      {list.isPending ? (
        <Spinner label="Loading" />
      ) : list.isError ? (
        <Alert tone="error">{errorMessage(list.error)}</Alert>
      ) : items.length === 0 ? (
        <EmptyState
          title={search ? "No matches" : `No ${m.plural_label.toLowerCase()} yet`}
          description={search ? "Try another search." : undefined}
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-300 bg-white">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-600">
                {columns.map((c) => (
                  <th key={c} className="px-4 py-2">
                    {label(m, c)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.map((r) => (
                <tr key={r.id} className="hover:bg-slate-50">
                  {columns.map((c) => (
                    <td key={c} className="px-4 py-2">
                      {c === "name" ? (
                        <Link
                          to={`/portal/o/${object}/${r.id}`}
                          className="font-medium text-brand-700 hover:underline"
                        >
                          {r.name}
                        </Link>
                      ) : (
                        <Value meta={m} record={r} api={c} />
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {list.hasNextPage && (
        <div className="text-center">
          <Button
            variant="secondary"
            loading={list.isFetchingNextPage}
            onClick={() => void list.fetchNextPage()}
          >
            Load more
          </Button>
        </div>
      )}
    </div>
  );
}

// ================================================================ record

export function PortalRecordPage() {
  const { object = "", id = "" } = useParams();
  const meta = useDescribe(object);
  const record = useQuery({
    queryKey: ["portal", "record", object, id],
    queryFn: ({ signal }) => portalApi.get(object, id, signal),
  });
  const [action, setAction] = useState<{ name: string; label: string } | null>(null);
  if (meta.isPending || record.isPending) return <Spinner label="Loading" />;
  if (meta.isError) return <Alert tone="error">{errorMessage(meta.error)}</Alert>;
  if (record.isError) return <Alert tone="error">{errorMessage(record.error)}</Alert>;
  const m = meta.data;
  const r = record.data;
  const highlights = m.compact_layout.filter((f) => f !== "name");
  const status = (r.fields.status as string | undefined) ?? undefined;
  const showPdf = PDF_OBJECTS.has(object) && status !== "Draft";
  return (
    <div className="space-y-4">
      <nav aria-label="Breadcrumb" className="text-xs text-slate-500">
        <Link to="/portal" className="hover:underline">
          Home
        </Link>{" "}
        /{" "}
        <Link to={`/portal/o/${object}`} className="hover:underline">
          {m.plural_label}
        </Link>
      </nav>
      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <ObjectIcon icon={m.icon} color={m.color} size={40} />
            <div>
              <p className="text-xs text-slate-500">{m.label}</p>
              <h1 className="text-xl font-semibold text-slate-900">{r.name}</h1>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {r.actions.map((a) => (
              <Button key={a.name} onClick={() => setAction(a)}>
                {a.label}
              </Button>
            ))}
            {showPdf && (
              <a
                href={`${API_BASE}/portal/objects/${object}/records/${id}/pdf`}
                className="inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                <DownloadIcon size={14} /> Download PDF
              </a>
            )}
          </div>
        </div>
        {highlights.length > 0 && (
          <dl className="mt-4 grid gap-3 border-t border-slate-100 pt-3 text-sm sm:grid-cols-4">
            {highlights.map((f) => (
              <div key={f}>
                <dt className="text-xs text-slate-500">{label(m, f)}</dt>
                <dd>
                  <Value meta={m} record={r} api={f} />
                </dd>
              </div>
            ))}
          </dl>
        )}
      </section>
      {m.page_layout.map((s) => (
        <section key={s.label} className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="font-semibold text-slate-900">{s.label}</h2>
          <dl className={cx("mt-3 grid gap-x-6 gap-y-3 text-sm", s.columns === 2 && "sm:grid-cols-2")}>
            {s.fields.map((f) => (
              <div key={f} className="border-b border-slate-100 pb-1">
                <dt className="text-xs text-slate-500">{label(m, f)}</dt>
                <dd className="min-h-5 whitespace-pre-wrap">
                  <Value meta={m} record={r} api={f} />
                </dd>
              </div>
            ))}
          </dl>
        </section>
      ))}
      {r.related.map((rel) => (
        <section key={rel.object} className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="font-semibold text-slate-900">
            {rel.label} ({rel.items.length})
          </h2>
          {rel.items.length === 0 ? (
            <p className="mt-2 text-sm text-slate-500">None</p>
          ) : (
            <ul className="mt-2 divide-y divide-slate-100 text-sm">
              {rel.items.map((it) => (
                <li key={it.id} className="py-2">
                  <Link
                    to={`/portal/o/${rel.object}/${it.id}`}
                    className="font-medium text-brand-700 hover:underline"
                  >
                    {it.name}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      ))}
      <Conversation object={object} record={r} />
      {action && <ActionModal object={object} id={id} action={action} onClose={() => setAction(null)} />}
    </div>
  );
}

function Conversation({ object, record }: { object: string; record: PortalRecord }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [body, setBody] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const refresh = () => void qc.invalidateQueries({ queryKey: ["portal", "record", object, record.id] });
  const comment = useMutation({
    mutationFn: () => portalApi.comment(object, record.id, body.trim()),
    onSuccess: () => {
      setBody("");
      refresh();
    },
  });
  const upload = useMutation({
    mutationFn: (file: File) =>
      uploadFile(file, { path: `/portal/objects/${object}/records/${record.id}/files` }),
    onSuccess: (f) => {
      toast.show(`${f.name} uploaded.`);
      refresh();
    },
    onError: (e) => toast.show(errorMessage(e), "error"),
  });
  const notes = record.timeline.note;
  const files = record.timeline.file;
  if (notes === undefined && files === undefined) return null;
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      {notes !== undefined && (
        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm lg:col-span-2">
          <h2 className="font-semibold text-slate-900">Conversation</h2>
          <ol className="mt-3 space-y-3">
            {notes.map((n) => (
              <li key={n.id} className="rounded-md bg-slate-50 p-3 text-sm">
                <p className="whitespace-pre-wrap text-slate-800">{String(n.fields.body ?? n.name)}</p>
                <p className="mt-1 text-xs text-slate-500">
                  {n.created_by?.name} · {formatDateTimeValue(n.created_at)}
                </p>
              </li>
            ))}
            {notes.length === 0 && <li className="text-sm text-slate-500">No messages yet.</li>}
          </ol>
          <form
            className="mt-3"
            onSubmit={(e) => {
              e.preventDefault();
              if (body.trim()) comment.mutate();
            }}
          >
            {comment.isError && (
              <Alert tone="error" className="mb-2">
                {errorMessage(comment.error)}
              </Alert>
            )}
            <label htmlFor="portal-comment" className="text-sm font-medium text-slate-700">
              Add a message
            </label>
            <textarea
              id="portal-comment"
              rows={3}
              className={cx(controlClass(false), "mt-1")}
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
            <div className="mt-2 flex justify-end">
              <Button type="submit" loading={comment.isPending} disabled={!body.trim()}>
                Send
              </Button>
            </div>
          </form>
        </section>
      )}
      {files !== undefined && (
        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="flex items-center justify-between font-semibold text-slate-900">
            Files
            <Button
              size="sm"
              variant="secondary"
              loading={upload.isPending}
              onClick={() => fileInput.current?.click()}
            >
              <UploadIcon size={14} /> Upload
            </Button>
          </h2>
          <input
            ref={fileInput}
            type="file"
            className="sr-only"
            aria-label="Upload a file"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) upload.mutate(f);
              e.target.value = "";
            }}
          />
          <ul className="mt-3 space-y-2 text-sm">
            {files.map((f) => (
              <li key={f.id} className="flex items-center gap-2">
                <PaperclipIcon size={14} className="text-slate-400" />
                <a href={fileUrl(f.id, false, true)} className="truncate text-brand-700 hover:underline">
                  {f.name}
                </a>
              </li>
            ))}
            {files.length === 0 && <li className="text-slate-500">No files yet.</li>}
          </ul>
        </section>
      )}
    </div>
  );
}

function ActionModal({
  object,
  id,
  action,
  onClose,
}: {
  object: string;
  id: string;
  action: { name: string; label: string };
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const { me } = useAuth();
  const isSign = action.name === "sign";
  const [fullName, setFullName] = useState(me?.user.name ?? "");
  const [accept, setAccept] = useState(false);
  const run = useMutation({
    mutationFn: () =>
      portalApi.action(object, id, action.name, isSign ? { full_name: fullName.trim(), accept } : {}),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["portal"] });
      toast.show(isSign ? "Signed. Thank you." : `${action.label} done.`);
      onClose();
    },
  });
  return (
    <Modal
      open
      onClose={onClose}
      size="sm"
      title={action.label}
      busy={run.isPending}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => run.mutate()}
            loading={run.isPending}
            disabled={isSign && (fullName.trim().length < 3 || !accept)}
          >
            {isSign ? "Sign" : "Confirm"}
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        {run.isError && <Alert tone="error">{errorMessage(run.error)}</Alert>}
        {isSign ? (
          <>
            <p className="text-sm text-slate-700">
              Read the document above. Typing your full name and ticking the box signs it electronically; the
              date, time and your IP address are recorded.
            </p>
            <FormField label="Full name" required>
              {({ id: fid }) => (
                <Input id={fid} value={fullName} onChange={(e) => setFullName(e.target.value)} />
              )}
            </FormField>
            <Checkbox
              label="I have read and accept this agreement."
              checked={accept}
              onChange={(e) => setAccept(e.target.checked)}
            />
          </>
        ) : (
          <p className="text-sm text-slate-700">Continue with “{action.label}”?</p>
        )}
      </div>
    </Modal>
  );
}

// ================================================================ new case

export function PortalNewCasePage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const meta = useDescribe("case");
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("");
  const [type, setType] = useState("");
  const create = useMutation({
    mutationFn: () =>
      portalApi.createCase({
        subject: subject.trim(),
        description: description.trim() || undefined,
        priority: priority || undefined,
        type: type || undefined,
      }),
    onSuccess: (c) => {
      void qc.invalidateQueries({ queryKey: ["portal"] });
      navigate(`/portal/o/case/${c.id}`);
    },
  });
  const values = (f: string) => (meta.data?.fields[f]?.options.values ?? []).filter((v) => v.active);
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <nav aria-label="Breadcrumb" className="text-xs text-slate-500">
        <Link to="/portal" className="hover:underline">
          Home
        </Link>{" "}
        / New case
      </nav>
      <h1 className="text-2xl font-semibold text-slate-900">How can we help?</h1>
      <form
        className="space-y-3 rounded-lg border border-slate-200 bg-white p-5 shadow-sm"
        onSubmit={(e) => {
          e.preventDefault();
          if (subject.trim()) create.mutate();
        }}
      >
        {create.isError && <Alert tone="error">{errorMessage(create.error)}</Alert>}
        <FormField label="Subject" required>
          {({ id }) => (
            <Input id={id} value={subject} maxLength={255} onChange={(e) => setSubject(e.target.value)} />
          )}
        </FormField>
        <FormField label="Description" hint="Tell us what happened and what you need.">
          {({ id }) => (
            <textarea
              id={id}
              rows={6}
              className={controlClass(false)}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          )}
        </FormField>
        <div className="grid gap-3 sm:grid-cols-2">
          {values("priority").length > 0 && (
            <FormField label="Priority">
              {({ id }) => (
                <select
                  id={id}
                  className={controlClass(false)}
                  value={priority}
                  onChange={(e) => setPriority(e.target.value)}
                >
                  <option value="">Normal</option>
                  {values("priority").map((v) => (
                    <option key={v.value} value={v.value}>
                      {v.label}
                    </option>
                  ))}
                </select>
              )}
            </FormField>
          )}
          {values("type").length > 0 && (
            <FormField label="Type">
              {({ id }) => (
                <select
                  id={id}
                  className={controlClass(false)}
                  value={type}
                  onChange={(e) => setType(e.target.value)}
                >
                  <option value="">Choose…</option>
                  {values("type").map((v) => (
                    <option key={v.value} value={v.value}>
                      {v.label}
                    </option>
                  ))}
                </select>
              )}
            </FormField>
          )}
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" type="button" onClick={() => navigate(-1)}>
            Cancel
          </Button>
          <Button type="submit" loading={create.isPending} disabled={!subject.trim()}>
            Submit
          </Button>
        </div>
      </form>
    </div>
  );
}

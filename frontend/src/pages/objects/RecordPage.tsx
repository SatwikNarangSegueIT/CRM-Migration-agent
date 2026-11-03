import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, errorMessage } from "../../api/client";
import { fileUrl, recordsApi, uploadFile } from "../../api/records";
import { setupApi } from "../../api/setup";
import type { ObjectDescribe, RecordData, RelatedList } from "../../api/types";
import { useAuth } from "../../auth/context";
import { ActionDialog } from "../../components/record/ActionDialog";
import { ChangeOwnerDialog } from "../../components/record/ChangeOwnerDialog";
import { FieldDisplay } from "../../components/record/FieldDisplay";
import { ObjectIcon } from "../../components/record/ObjectIcon";
import { Path } from "../../components/record/Path";
import { PrivacyDialog } from "../../components/record/PrivacyDialog";
import { RecordFormModal } from "../../components/record/RecordFormModal";
import { ChevronDownIcon, DownloadIcon, EditIcon, PaperclipIcon, RecycleIcon } from "../../components/icons";
import { Alert, Button, ConfirmDialog, Spinner, useToast } from "../../components/ui";
import { cx } from "../../components/ui/cx";
import { formatDateTimeValue, recordPath, useObjectMeta } from "../../lib/records";
import { NotFoundPage } from "../NotFoundPage";
import { ActivityPanel } from "./ActivityPanel";
import { MenuItem } from "./ObjectListPage";
import { SharingPanel } from "./SharingPanel";
import { useDismiss } from "../../lib/useDismiss";

export function RecordPage() {
  const { object = "", id = "" } = useParams();
  const meta = useObjectMeta(object);
  const record = useQuery({
    queryKey: ["record", object, id],
    queryFn: ({ signal }) => recordsApi.get(object, id, signal),
    enabled: meta.isSuccess,
  });
  if (meta.isPending || (meta.isSuccess && record.isPending)) return <Spinner label="Loading record" />;
  const error = meta.error ?? record.error;
  if (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 403)) return <NotFoundPage />;
    return <Alert tone="error">{errorMessage(error)}</Alert>;
  }
  return <RecordView key={id} meta={meta.data!} record={record.data!} />;
}

function MoreMenu({ children }: { children: (close: () => void) => React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useDismiss(open, ref, () => setOpen(false));
  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-label="More actions"
        aria-haspopup="menu"
        aria-expanded={open}
        className="inline-flex h-[34px] items-center rounded-md border border-slate-300 bg-white px-2 text-slate-600 shadow-sm hover:bg-slate-50"
        onClick={() => setOpen((o) => !o)}
      >
        <ChevronDownIcon size={16} />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 z-30 mt-1 w-56 rounded-md border border-slate-200 bg-white py-1 text-sm shadow-lg"
        >
          {children(() => setOpen(false))}
        </div>
      )}
    </div>
  );
}

function RecordView({ meta, record }: { meta: ObjectDescribe; record: RecordData }) {
  const api = meta.api_name;
  const { can } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"details" | "related" | "activity" | "history">("details");
  const [editing, setEditing] = useState(false);
  const [cloning, setCloning] = useState(false);
  const [ownerOpen, setOwnerOpen] = useState(false);
  const [sharingOpen, setSharingOpen] = useState(false);
  const [privacy, setPrivacy] = useState<"export" | "erase" | null>(null);
  const [confirm, setConfirm] = useState<"delete" | null>(null);
  const [action, setAction] = useState<{ name: string; label: string } | null>(null);

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["record", api, record.id] });
    void queryClient.invalidateQueries({ queryKey: ["related"] });
    void queryClient.invalidateQueries({ queryKey: ["activities"] });
    void queryClient.invalidateQueries({ queryKey: ["history", api, record.id] });
  };
  const markStage = useMutation({
    mutationFn: (value: string) =>
      recordsApi.update(api, record.id, { version: record.version, fields: { [meta.path_field!]: value } }),
    onSuccess: () => {
      toast.show(`${meta.fields[meta.path_field!]!.label} updated.`);
      refresh();
    },
    onError: (e) => {
      if (e instanceof ApiError && e.fields.loss_reason) {
        toast.show("Choose a loss reason in Edit before closing as lost.", "error");
        setEditing(true);
      } else toast.show(errorMessage(e), "error");
    },
  });
  const remove = useMutation({
    mutationFn: () => recordsApi.remove(api, record.id),
    onSuccess: () => {
      toast.show(`${meta.label} "${record.name}" was deleted.`);
      void queryClient.invalidateQueries({ queryKey: ["records", api] });
      navigate(`/o/${api}`);
    },
    onError: (e) => {
      setConfirm(null);
      toast.show(errorMessage(e), "error");
    },
  });
  const restore = useMutation({
    mutationFn: () => recordsApi.restore(api, record.id),
    onSuccess: () => {
      toast.show("Record restored.");
      refresh();
    },
    onError: (e) => toast.show(errorMessage(e), "error"),
  });
  const invite = useMutation({
    mutationFn: () => setupApi.invitePortalUser(record.id),
    onSuccess: (u) => toast.show(`Portal invitation sent to ${u.email}.`),
    onError: (e) => toast.show(errorMessage(e), "error"),
  });

  const compact = meta.compact_layout.filter((f) => meta.fields[f]);
  const pathField = meta.path_field ? meta.fields[meta.path_field] : undefined;
  const actions = record.actions ?? [];
  const primaryActions = actions.filter((a) => a.name !== "mark_stage").slice(0, 3);
  const moreActions = actions.filter((a) => a.name !== "mark_stage").slice(3);
  const hasRelated = meta.related_lists.length > 0;
  const hasActivity = meta.activity_objects.length > 0;

  return (
    <div className="space-y-3">
      {record.is_deleted && (
        <Alert tone="warning" title="This record is in the recycle bin">
          <Button
            size="sm"
            variant="secondary"
            className="mt-2"
            loading={restore.isPending}
            onClick={() => restore.mutate()}
          >
            <RecycleIcon size={14} /> Restore
          </Button>
        </Alert>
      )}
      {/* Highlights panel */}
      <section aria-label="Highlights" className="rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3 px-4 pt-4">
          <div className="flex min-w-0 items-center gap-3">
            <ObjectIcon icon={meta.icon} color={meta.color} size={40} />
            <div className="min-w-0">
              <p className="text-xs text-slate-600">
                <Link to={`/o/${api}`} className="hover:underline">
                  {meta.label}
                </Link>
              </p>
              <h1 className="truncate text-xl font-bold text-slate-900">{record.name}</h1>
            </div>
          </div>
          {!record.is_deleted && (
            <div className="flex flex-wrap items-center gap-2">
              {record.access.edit && (
                <Button variant="secondary" onClick={() => setEditing(true)}>
                  <EditIcon size={16} /> Edit
                </Button>
              )}
              {primaryActions.map((a) => (
                <Button key={a.name} variant="secondary" onClick={() => setAction(a)}>
                  {a.label}
                </Button>
              ))}
              {(api === "invoice" || api === "quote") && (
                <a
                  className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50"
                  href={`/api/v1/objects/${api}/records/${record.id}/pdf`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <DownloadIcon size={16} /> PDF
                </a>
              )}
              <MoreMenu>
                {(close) => (
                  <>
                    {moreActions.map((a) => (
                      <MenuItem
                        key={a.name}
                        onClick={() => {
                          close();
                          setAction(a);
                        }}
                      >
                        {a.label}
                      </MenuItem>
                    ))}
                    {meta.access.create && meta.name_field_type !== "auto_number" && (
                      <MenuItem
                        onClick={() => {
                          close();
                          setCloning(true);
                        }}
                      >
                        Clone
                      </MenuItem>
                    )}
                    {record.access.edit && (
                      <MenuItem
                        onClick={() => {
                          close();
                          setOwnerOpen(true);
                        }}
                      >
                        Change Owner
                      </MenuItem>
                    )}
                    <MenuItem
                      onClick={() => {
                        close();
                        setSharingOpen(true);
                      }}
                    >
                      Sharing
                    </MenuItem>
                    {api === "contact" && can("manage_portal_users") && (
                      <MenuItem
                        onClick={() => {
                          close();
                          invite.mutate();
                        }}
                      >
                        Invite to Customer Portal
                      </MenuItem>
                    )}
                    {(api === "contact" || api === "lead") && can("manage_users") && (
                      <>
                        <MenuItem
                          onClick={() => {
                            close();
                            setPrivacy("export");
                          }}
                        >
                          Export Personal Data
                        </MenuItem>
                        <MenuItem
                          danger
                          onClick={() => {
                            close();
                            setPrivacy("erase");
                          }}
                        >
                          Erase Personal Data
                        </MenuItem>
                      </>
                    )}
                    {record.access.delete && (
                      <MenuItem
                        danger
                        onClick={() => {
                          close();
                          setConfirm("delete");
                        }}
                      >
                        Delete
                      </MenuItem>
                    )}
                  </>
                )}
              </MoreMenu>
            </div>
          )}
        </div>
        <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 border-t border-slate-100 px-4 py-3 text-sm sm:grid-cols-3 lg:grid-cols-5">
          {compact.map((api_) => (
            <div key={api_} className="min-w-0">
              <dt className="text-xs text-slate-500">
                {api_ === "owner_id" ? "Owner" : meta.fields[api_]?.label}
              </dt>
              <dd className="truncate text-slate-900">
                <FieldDisplay field={meta.fields[api_]} record={record} apiName={api_} />
              </dd>
            </div>
          ))}
        </dl>
      </section>

      {pathField && (
        <Path
          field={pathField}
          value={record.fields[pathField.api_name]}
          canEdit={
            record.access.edit && !record.is_deleted && pathField.access === "edit" && !pathField.is_readonly
          }
          saving={markStage.isPending}
          onMark={(v) => markStage.mutate(v)}
        />
      )}

      <div className="grid gap-3 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
            <div
              role="tablist"
              aria-label="Record tabs"
              className="flex gap-1 border-b border-slate-200 px-3"
            >
              {(["details", ...(hasRelated ? ["related"] : []), "history"] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  role="tab"
                  aria-selected={tab === t}
                  className={cx(
                    "border-b-[3px] px-3 py-3 text-sm capitalize",
                    tab === t
                      ? "border-brand-700 font-semibold text-slate-900"
                      : "border-transparent text-slate-600 hover:text-slate-900",
                  )}
                  onClick={() => setTab(t as typeof tab)}
                >
                  {t}
                </button>
              ))}
              {hasActivity && (
                <button
                  type="button"
                  role="tab"
                  aria-selected={tab === "activity"}
                  className={cx(
                    "border-b-[3px] px-3 py-3 text-sm lg:hidden",
                    tab === "activity"
                      ? "border-brand-700 font-semibold text-slate-900"
                      : "border-transparent text-slate-600",
                  )}
                  onClick={() => setTab("activity")}
                >
                  Activity
                </button>
              )}
            </div>
            <div className="p-4" role="tabpanel">
              {tab === "details" && (
                <DetailsTab meta={meta} record={record} onEdit={() => setEditing(true)} />
              )}
              {tab === "related" && <RelatedTab meta={meta} record={record} />}
              {tab === "history" && <HistoryTab meta={meta} record={record} />}
              {tab === "activity" && (
                <div className="lg:hidden">
                  <ActivityPanel meta={meta} record={record} />
                </div>
              )}
            </div>
          </div>
        </div>
        <div className="space-y-3">
          {hasActivity && (
            <div className="hidden lg:block">
              <ActivityPanel meta={meta} record={record} />
            </div>
          )}
          {hasRelated &&
            tab !== "related" &&
            meta.related_lists
              .slice(0, 3)
              .map((rl) => (
                <RelatedCard
                  key={`${rl.object}.${rl.field}`}
                  parent={record}
                  parentMeta={meta}
                  list={rl}
                  compact
                />
              ))}
        </div>
      </div>

      {(editing || cloning) && (
        <RecordFormModal
          meta={meta}
          record={editing ? record : null}
          defaults={
            cloning
              ? Object.fromEntries(
                  Object.entries(record.fields).filter(
                    ([k]) => meta.fields[k]?.access === "edit" && !meta.fields[k]?.is_readonly,
                  ),
                )
              : {}
          }
          defaultNames={
            cloning ? Object.fromEntries(Object.entries(record.display).map(([k, v]) => [k, v.name])) : {}
          }
          open
          onClose={() => {
            setEditing(false);
            setCloning(false);
          }}
          onSaved={(r) => {
            setEditing(false);
            setCloning(false);
            toast.show(`${meta.label} "${r.name}" was saved.`);
            if (cloning) navigate(recordPath(api, r.id));
            else refresh();
          }}
        />
      )}
      {ownerOpen && (
        <ChangeOwnerDialog
          object={api}
          ids={[record.id]}
          allowQueues={meta.allow_queues}
          onClose={() => setOwnerOpen(false)}
          onDone={(m) => {
            setOwnerOpen(false);
            toast.show(m);
            refresh();
          }}
        />
      )}
      {sharingOpen && <SharingPanel object={api} record={record} onClose={() => setSharingOpen(false)} />}
      {privacy && (
        <PrivacyDialog
          object={api}
          record={record}
          mode={privacy}
          onClose={() => setPrivacy(null)}
          onErased={() => {
            setPrivacy(null);
            toast.show("Personal data erased.");
            refresh();
          }}
        />
      )}
      <ActionDialog
        object={api}
        record={record}
        action={action}
        onClose={() => setAction(null)}
        onDone={(result) => {
          const label = action?.label;
          setAction(null);
          toast.show(`${label} completed.`);
          if (typeof result.invoice_id === "string") navigate(recordPath("invoice", result.invoice_id));
          else refresh();
        }}
      />
      <ConfirmDialog
        open={confirm === "delete"}
        title={`Delete ${meta.label}?`}
        tone="danger"
        confirmLabel="Delete"
        loading={remove.isPending}
        onCancel={() => setConfirm(null)}
        onConfirm={() => remove.mutate()}
      >
        "{record.name}" goes to the recycle bin for 30 days
        {meta.related_lists.length ? ", together with its detail records" : ""}.
      </ConfirmDialog>
    </div>
  );
}

function DetailsTab({
  meta,
  record,
  onEdit,
}: {
  meta: ObjectDescribe;
  record: RecordData;
  onEdit: () => void;
}) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  return (
    <div className="space-y-4">
      {meta.page_layout.map((section) => {
        const open = !collapsed.has(section.label);
        return (
          <section key={section.label}>
            <h2>
              <button
                type="button"
                aria-expanded={open}
                className="flex w-full items-center gap-2 rounded bg-slate-100 px-3 py-1.5 text-left text-sm font-semibold text-slate-800"
                onClick={() =>
                  setCollapsed((c) => {
                    const n = new Set(c);
                    if (n.has(section.label)) n.delete(section.label);
                    else n.add(section.label);
                    return n;
                  })
                }
              >
                <ChevronDownIcon size={14} className={cx("transition-transform", !open && "-rotate-90")} />
                {section.label}
              </button>
            </h2>
            {open && (
              <dl className={cx("mt-2 grid gap-x-8", section.columns === 2 ? "sm:grid-cols-2" : "")}>
                {section.fields.map((api) => {
                  const f = meta.fields[api];
                  const editable =
                    record.access.edit && f && f.access === "edit" && !f.is_readonly && !f.is_system;
                  return (
                    <div
                      key={api}
                      className="group flex items-start justify-between gap-2 border-b border-slate-100 py-2"
                    >
                      <div className="min-w-0 flex-1">
                        <dt className="text-xs text-slate-500">
                          {api === "owner_id" ? "Owner" : (f?.label ?? api)}
                        </dt>
                        <dd className="min-h-[1.25rem] text-sm text-slate-900">
                          <FieldDisplay field={f} record={record} apiName={api} />
                        </dd>
                      </div>
                      {editable && (
                        <button
                          type="button"
                          aria-label={`Edit ${f.label}`}
                          className="invisible mt-3 rounded p-0.5 text-slate-400 hover:text-brand-700 group-hover:visible focus:visible"
                          onClick={onEdit}
                        >
                          <EditIcon size={14} />
                        </button>
                      )}
                    </div>
                  );
                })}
              </dl>
            )}
          </section>
        );
      })}
    </div>
  );
}

export function RelatedCard({
  parent,
  parentMeta,
  list,
  compact = false,
}: {
  parent: RecordData;
  parentMeta: ObjectDescribe;
  list: RelatedList;
  compact?: boolean;
}) {
  const childMeta = useObjectMeta(list.object);
  const toast = useToast();
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [limit, setLimit] = useState(compact ? 3 : 5);
  const rows = useQuery({
    queryKey: ["related", parent.id, list.object, list.field, limit],
    queryFn: ({ signal }) =>
      recordsApi.related(parentMeta.api_name, parent.id, list.object, list.field, limit, null, signal),
  });
  const total = rows.data?.total ?? 0;
  const cols = list.columns.filter((c) => childMeta.data?.fields[c]);
  return (
    <section aria-label={list.label} className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <header className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
          {childMeta.data && <ObjectIcon icon={childMeta.data.icon} color={childMeta.data.color} size={22} />}
          {list.label} ({rows.data ? `${total}${rows.data.total_capped ? "+" : ""}` : "…"})
        </h3>
        {list.can_create && childMeta.data && !parent.is_deleted && (
          <Button size="sm" variant="secondary" onClick={() => setCreating(true)}>
            New
          </Button>
        )}
      </header>
      {rows.isPending ? (
        <div className="p-4">
          <Spinner label="Loading" />
        </div>
      ) : rows.isError ? (
        <p className="p-4 text-sm text-red-700">{errorMessage(rows.error)}</p>
      ) : total === 0 ? (
        <p className="px-4 py-3 text-sm text-slate-500">No {list.label.toLowerCase()} yet.</p>
      ) : compact ? (
        <ul className="divide-y divide-slate-100">
          {rows.data.items.map((r) => (
            <li key={r.id} className="px-4 py-2 text-sm">
              <Link to={recordPath(list.object, r.id)} className="font-medium text-brand-700 hover:underline">
                {r.name}
              </Link>
              <dl className="mt-0.5 grid grid-cols-[auto_1fr] gap-x-2 text-xs text-slate-600">
                {cols
                  .filter((c) => c !== "name")
                  .slice(0, 3)
                  .map((c) => (
                    <div key={c} className="contents">
                      <dt>{childMeta.data?.fields[c]?.label}:</dt>
                      <dd className="truncate">
                        <FieldDisplay field={childMeta.data?.fields[c]} record={r} apiName={c} />
                      </dd>
                    </div>
                  ))}
              </dl>
            </li>
          ))}
        </ul>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-600">
                <th scope="col" className="px-4 py-2 font-semibold">
                  {childMeta.data?.fields.name?.label ?? "Name"}
                </th>
                {cols
                  .filter((c) => c !== "name")
                  .map((c) => (
                    <th key={c} scope="col" className="px-4 py-2 font-semibold">
                      {childMeta.data?.fields[c]?.label}
                    </th>
                  ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.data.items.map((r) => (
                <tr key={r.id}>
                  <td className="px-4 py-2">
                    <Link to={recordPath(list.object, r.id)} className="text-brand-700 hover:underline">
                      {r.name}
                    </Link>
                  </td>
                  {cols
                    .filter((c) => c !== "name")
                    .map((c) => (
                      <td key={c} className="px-4 py-2">
                        <FieldDisplay field={childMeta.data?.fields[c]} record={r} apiName={c} />
                      </td>
                    ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {rows.data && total > rows.data.items.length && (
        <footer className="border-t border-slate-100 px-4 py-2 text-center">
          <button
            type="button"
            className="text-sm text-brand-700 hover:underline"
            onClick={() => setLimit(200)}
          >
            View All
          </button>
        </footer>
      )}
      {creating && childMeta.data && (
        <RecordFormModal
          meta={childMeta.data}
          record={null}
          defaults={{ [list.field]: parent.id }}
          defaultNames={{ [list.field]: parent.name }}
          open
          onClose={() => setCreating(false)}
          onSaved={(r) => {
            setCreating(false);
            toast.show(`${childMeta.data!.label} "${r.name}" was created.`);
            void queryClient.invalidateQueries({ queryKey: ["related", parent.id] });
            void queryClient.invalidateQueries({ queryKey: ["record", parentMeta.api_name, parent.id] });
          }}
        />
      )}
    </section>
  );
}

function RelatedTab({ meta, record }: { meta: ObjectDescribe; record: RecordData }) {
  return (
    <div className="space-y-3">
      {meta.related_lists.map((rl) => (
        <RelatedCard key={`${rl.object}.${rl.field}`} parent={record} parentMeta={meta} list={rl} />
      ))}
      {meta.allow_files && <FilesCard object={meta.api_name} record={record} />}
    </div>
  );
}

export function FilesCard({ object, record }: { object: string; record: RecordData }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const files = useQuery({
    queryKey: ["related", record.id, "file", "related_to"],
    queryFn: ({ signal }) => recordsApi.related(object, record.id, "file", "related_to", 50, null, signal),
  });
  const upload = useMutation({
    mutationFn: (f: File) => uploadFile(f, { relatedTo: record.id }),
    onSuccess: (r) => {
      toast.show(`${r.name} uploaded.`);
      void queryClient.invalidateQueries({ queryKey: ["related", record.id] });
      void queryClient.invalidateQueries({ queryKey: ["activities"] });
    },
    onError: (e) => toast.show(errorMessage(e), "error"),
  });
  return (
    <section aria-label="Files" className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <header className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
          <PaperclipIcon size={16} /> Files ({files.data?.total ?? "…"})
        </h3>
        <Button
          size="sm"
          variant="secondary"
          loading={upload.isPending}
          onClick={() => input.current?.click()}
        >
          Upload
        </Button>
        <input
          ref={input}
          type="file"
          className="sr-only"
          aria-label="Upload file"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) upload.mutate(f);
            e.target.value = "";
          }}
        />
      </header>
      <ul className="divide-y divide-slate-100">
        {files.data?.items.map((f) => (
          <li key={f.id} className="flex items-center justify-between px-4 py-2 text-sm">
            <a
              href={fileUrl(f.id, true)}
              target="_blank"
              rel="noopener noreferrer"
              className="truncate text-brand-700 hover:underline"
            >
              {f.name}
            </a>
            <span className="flex-none text-xs text-slate-500">{formatDateTimeValue(f.created_at)}</span>
          </li>
        ))}
        {files.data?.total === 0 && <li className="px-4 py-3 text-sm text-slate-500">No files yet.</li>}
      </ul>
    </section>
  );
}

function HistoryTab({ meta, record }: { meta: ObjectDescribe; record: RecordData }) {
  const history = useQuery({
    queryKey: ["history", meta.api_name, record.id],
    queryFn: ({ signal }) => recordsApi.history(meta.api_name, record.id, signal),
  });
  if (history.isPending) return <Spinner label="Loading history" />;
  if (history.isError) return <Alert tone="error">{errorMessage(history.error)}</Alert>;
  if (history.data.length === 0)
    return (
      <p className="text-sm text-slate-500">
        No tracked changes yet. Fields with history tracking appear here when they change.
      </p>
    );
  const show = (field: string, v: unknown) => {
    const f = meta.fields[field];
    if (v === null || v === undefined || v === "") return <span className="text-slate-400">blank</span>;
    if (f?.type === "picklist") return f.options.values?.find((x) => x.value === v)?.label ?? String(v);
    if (typeof v === "object") return JSON.stringify(v);
    return String(v);
  };
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-slate-600">
            <th scope="col" className="px-3 py-2">
              Date
            </th>
            <th scope="col" className="px-3 py-2">
              Field
            </th>
            <th scope="col" className="px-3 py-2">
              User
            </th>
            <th scope="col" className="px-3 py-2">
              Original value
            </th>
            <th scope="col" className="px-3 py-2">
              New value
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {history.data.map((h) => (
            <tr key={h.id}>
              <td className="whitespace-nowrap px-3 py-2">{formatDateTimeValue(h.changed_at)}</td>
              <td className="px-3 py-2">{h.field_label}</td>
              <td className="px-3 py-2">{h.changed_by ?? "System"}</td>
              <td className="px-3 py-2">{show(h.field, h.old_value)}</td>
              <td className="px-3 py-2">{show(h.field, h.new_value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

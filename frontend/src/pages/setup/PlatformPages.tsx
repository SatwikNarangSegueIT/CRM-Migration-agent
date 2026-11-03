// Setup → App Manager, Industry Packs and Portal Users.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, errorMessage } from "../../api/client";
import { recordsApi } from "../../api/records";
import { setupApi, type PackInfo, type PortalUser, type SetupApp } from "../../api/setup";
import { useAuth } from "../../auth/context";
import { AppsIcon, PackageIcon, PlusIcon, UsersIcon } from "../../components/icons";
import { Combobox, controlClass } from "../../components/record/FieldInput";
import { ObjectIcon } from "../../components/record/ObjectIcon";
import {
  Alert,
  Badge,
  Button,
  Checkbox,
  ConfirmDialog,
  EmptyState,
  FormField,
  Input,
  PageHeader,
  Spinner,
  useToast,
} from "../../components/ui";
import { cx } from "../../components/ui/cx";
import { Modal } from "../../components/ui/Modal";
import { formatDateTimeValue } from "../../lib/records";
import { IconColorPicker } from "./ObjectManagerPages";

// ================================================================ apps

type TabSpec = { kind: string; object?: string };
const SPECIAL_TABS: { kind: string; label: string }[] = [
  { kind: "home", label: "Home" },
  { kind: "calendar", label: "Calendar" },
  { kind: "reports", label: "Reports" },
  { kind: "dashboards", label: "Dashboards" },
  { kind: "queues", label: "Queues" },
];

function tabKey(t: TabSpec) {
  return t.kind === "object" ? `object:${t.object}` : t.kind;
}

export function AppManagerPage() {
  const canEdit = useAuth().can("customize_application");
  const apps = useQuery({ queryKey: ["setup", "apps"], queryFn: ({ signal }) => setupApi.apps(signal) });
  const [editing, setEditing] = useState<SetupApp | "new" | null>(null);
  return (
    <div>
      <PageHeader
        title="App Manager"
        subtitle="Apps group object tabs in the app rail. Choose the tabs, their order and which profiles see each app."
        icon={<AppsIcon size={22} className="text-brand-700" />}
        actions={
          canEdit && (
            <Button onClick={() => setEditing("new")}>
              <PlusIcon size={16} /> New App
            </Button>
          )
        }
      />
      {apps.isPending ? (
        <Spinner label="Loading apps" />
      ) : apps.isError ? (
        <Alert tone="error">{errorMessage(apps.error)}</Alert>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-300 bg-white">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-600">
                <th className="px-4 py-2">App</th>
                <th className="px-4 py-2">Tabs</th>
                <th className="px-4 py-2">Visible to</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {[...apps.data]
                .sort((a, b) => a.sort_order - b.sort_order || a.label.localeCompare(b.label))
                .map((a) => (
                  <tr key={a.id}>
                    <td className="px-4 py-2">
                      <span className="inline-flex items-center gap-2 font-medium text-slate-900">
                        <ObjectIcon icon={a.icon} color={a.color} size={24} />
                        {a.label}
                        {a.pack_key && <Badge tone="purple">Pack</Badge>}
                      </span>
                      {a.description && <p className="mt-0.5 text-xs text-slate-500">{a.description}</p>}
                    </td>
                    <td className="px-4 py-2 text-slate-600">{a.tabs.length}</td>
                    <td className="px-4 py-2 text-slate-600">
                      {a.profile_ids.length ? `${a.profile_ids.length} profile(s)` : "Everyone"}
                    </td>
                    <td className="px-4 py-2">
                      {a.is_active ? <Badge tone="green">Active</Badge> : <Badge>Inactive</Badge>}
                    </td>
                    <td className="px-4 py-2 text-right">
                      {canEdit && (
                        <button
                          type="button"
                          className="text-sm font-medium text-brand-700 hover:underline"
                          onClick={() => setEditing(a)}
                        >
                          Edit
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}
      {editing && <AppModal app={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function AppModal({ app, onClose }: { app: SetupApp | null; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const objects = useQuery({
    queryKey: ["setup", "objects"],
    queryFn: ({ signal }) => setupApi.objects(signal),
  });
  const profiles = useQuery({
    queryKey: ["setup", "profiles"],
    queryFn: ({ signal }) => setupApi.profiles(signal),
  });
  const [label, setLabel] = useState(app?.label ?? "");
  const [description, setDescription] = useState(app?.description ?? "");
  const [icon, setIcon] = useState(app?.icon ?? "custom");
  const [color, setColor] = useState(app?.color ?? "#0176d3");
  const [active, setActive] = useState(app?.is_active ?? true);
  const [sortOrder, setSortOrder] = useState(String(app?.sort_order ?? 100));
  const [tabs, setTabs] = useState<TabSpec[]>(app?.tabs ?? [{ kind: "home" }]);
  const [profileIds, setProfileIds] = useState<string[]>(app?.profile_ids ?? []);
  const [adding, setAdding] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);

  const labels = useMemo(() => {
    const m: Record<string, string> = Object.fromEntries(SPECIAL_TABS.map((t) => [t.kind, t.label]));
    for (const o of objects.data ?? []) m[`object:${o.api_name}`] = o.plural_label;
    return m;
  }, [objects.data]);
  const used = new Set(tabs.map(tabKey));
  const choices = [
    ...SPECIAL_TABS.map((t) => ({ key: t.kind, label: t.label })),
    ...(objects.data ?? [])
      .filter((o) => !o.api_name.endsWith("_line") || o.is_custom)
      .sort((a, b) => a.plural_label.localeCompare(b.plural_label))
      .map((o) => ({ key: `object:${o.api_name}`, label: o.plural_label })),
  ].filter((c) => !used.has(c.key));

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["setup", "apps"] });
    void qc.invalidateQueries({ queryKey: ["meta", "apps"] });
  };
  const save = useMutation({
    mutationFn: () =>
      setupApi.saveApp(app?.id ?? null, {
        label,
        description: description.trim() || null,
        icon,
        color,
        is_active: active,
        sort_order: Number(sortOrder) || 0,
        tabs,
        profile_ids: profileIds,
      }),
    onSuccess: () => {
      invalidate();
      toast.show(app ? "App saved." : "App created.");
      onClose();
    },
  });
  const remove = useMutation({
    mutationFn: () => setupApi.deleteApp(app!.id),
    onSuccess: () => {
      invalidate();
      toast.show("App deleted.");
      onClose();
    },
  });
  const move = (i: number, d: -1 | 1) => {
    const j = i + d;
    if (j < 0 || j >= tabs.length) return;
    const next = [...tabs];
    [next[i], next[j]] = [next[j]!, next[i]!];
    setTabs(next);
  };
  const err = (k: string) => (save.error instanceof ApiError ? save.error.fields[k] : undefined);

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      busy={save.isPending}
      title={app ? `Edit ${app.label}` : "New app"}
      footer={
        <div className="flex w-full justify-between">
          {app && !app.pack_key ? (
            <Button variant="danger" onClick={() => setConfirmDelete(true)}>
              Delete
            </Button>
          ) : (
            <span />
          )}
          <span className="flex gap-2">
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button onClick={() => save.mutate()} loading={save.isPending} disabled={!label.trim()}>
              Save
            </Button>
          </span>
        </div>
      }
    >
      <div className="space-y-4">
        {save.isError && <Alert tone="error">{errorMessage(save.error)}</Alert>}
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="sm:col-span-2">
            <FormField label="App name" required error={err("label")}>
              {({ id }) => <Input id={id} value={label} onChange={(e) => setLabel(e.target.value)} />}
            </FormField>
          </div>
          <FormField label="Order in app rail" error={err("sort_order")}>
            {({ id }) => (
              <Input id={id} type="number" value={sortOrder} onChange={(e) => setSortOrder(e.target.value)} />
            )}
          </FormField>
        </div>
        <FormField label="Description">
          {({ id }) => (
            <textarea
              id={id}
              rows={2}
              className={controlClass(false)}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          )}
        </FormField>
        <IconColorPicker
          icon={icon}
          color={color}
          onChange={(i, c) => {
            setIcon(i);
            setColor(c);
          }}
        />
        <Checkbox
          label="Active (shown in the app rail)"
          checked={active}
          onChange={(e) => setActive(e.target.checked)}
        />
        <fieldset>
          <legend className="mb-1 text-sm font-semibold text-slate-800">Navigation tabs</legend>
          {err("tabs") && <p className="mb-1 text-sm text-red-700">{err("tabs")}</p>}
          <ol className="divide-y divide-slate-100 rounded-md border border-slate-200">
            {tabs.map((t, i) => (
              <li key={tabKey(t)} className="flex items-center justify-between px-3 py-1.5 text-sm">
                <span>{labels[tabKey(t)] ?? tabKey(t)}</span>
                <span className="whitespace-nowrap">
                  <button
                    type="button"
                    className="px-1 text-slate-600"
                    aria-label={`Move ${labels[tabKey(t)]} up`}
                    onClick={() => move(i, -1)}
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    className="px-1 text-slate-600"
                    aria-label={`Move ${labels[tabKey(t)]} down`}
                    onClick={() => move(i, 1)}
                  >
                    ↓
                  </button>
                  <button
                    type="button"
                    className="px-1 text-red-700"
                    aria-label={`Remove ${labels[tabKey(t)]}`}
                    onClick={() => setTabs(tabs.filter((_, k) => k !== i))}
                  >
                    ×
                  </button>
                </span>
              </li>
            ))}
            {tabs.length === 0 && <li className="px-3 py-2 text-sm text-slate-500">No tabs</li>}
          </ol>
          <div className="mt-2 flex gap-2">
            <select
              aria-label="Add tab"
              className={cx(controlClass(false), "max-w-xs")}
              value={adding}
              onChange={(e) => setAdding(e.target.value)}
            >
              <option value="">Add tab…</option>
              {choices.map((c) => (
                <option key={c.key} value={c.key}>
                  {c.label}
                </option>
              ))}
            </select>
            <Button
              size="sm"
              variant="secondary"
              disabled={!adding}
              onClick={() => {
                setTabs([
                  ...tabs,
                  adding.startsWith("object:")
                    ? { kind: "object", object: adding.slice(7) }
                    : { kind: adding },
                ]);
                setAdding("");
              }}
            >
              Add
            </Button>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Users only see tabs for objects their profile can read.
          </p>
        </fieldset>
        <fieldset>
          <legend className="mb-1 text-sm font-semibold text-slate-800">Visible to</legend>
          <p className="mb-2 text-xs text-slate-500">
            Leave all unticked to show the app to every staff profile.
          </p>
          <div className="grid gap-1 sm:grid-cols-2">
            {(profiles.data ?? [])
              .filter((p) => !p.is_portal)
              .map((p) => (
                <Checkbox
                  key={p.id}
                  label={p.name}
                  checked={profileIds.includes(p.id)}
                  onChange={(e) =>
                    setProfileIds(
                      e.target.checked ? [...profileIds, p.id] : profileIds.filter((x) => x !== p.id),
                    )
                  }
                />
              ))}
          </div>
        </fieldset>
      </div>
      <ConfirmDialog
        open={confirmDelete}
        title={`Delete ${app?.label ?? "app"}?`}
        tone="danger"
        confirmLabel="Delete app"
        loading={remove.isPending}
        onCancel={() => setConfirmDelete(false)}
        onConfirm={() => remove.mutate()}
      >
        {remove.isError && (
          <Alert tone="error" className="mb-2">
            {errorMessage(remove.error)}
          </Alert>
        )}
        Records are not affected; only the app and its navigation are removed.
      </ConfirmDialog>
    </Modal>
  );
}

// ================================================================ packs

const CONTENT_LABELS: Record<string, [string, string]> = {
  objects: ["object", "objects"],
  fields: ["field", "fields"],
  apps: ["app", "apps"],
  profiles: ["profile", "profiles"],
  list_views: ["list view", "list views"],
  reports: ["report", "reports"],
  dashboards: ["dashboard", "dashboards"],
  records: ["record", "records"],
};

function contentLabel(key: string, n: number): string {
  const [one, many] = CONTENT_LABELS[key] ?? [key.replace(/_/g, " "), key.replace(/_/g, " ")];
  return `${n} ${n === 1 ? one : many}`;
}

export function PacksPage() {
  const canManage = useAuth().can("manage_industry_packs");
  const qc = useQueryClient();
  const toast = useToast();
  const packs = useQuery({ queryKey: ["setup", "packs"], queryFn: ({ signal }) => setupApi.packs(signal) });
  const profiles = useQuery({
    queryKey: ["setup", "profiles"],
    queryFn: ({ signal }) => setupApi.profiles(signal),
  });
  const [confirm, setConfirm] = useState<{ pack: PackInfo; action: "install" | "enable" | "disable" } | null>(
    null,
  );
  const done = (data: PackInfo[], message: string) => {
    qc.setQueryData(["setup", "packs"], data);
    void qc.invalidateQueries({ queryKey: ["meta"] });
    void qc.invalidateQueries({ queryKey: ["setup"] });
    toast.show(message);
    setConfirm(null);
  };
  const act = useMutation({
    mutationFn: ({ pack, action }: { pack: PackInfo; action: "install" | "enable" | "disable" }) =>
      action === "install"
        ? setupApi.installPack(pack.key)
        : setupApi.enablePack(pack.key, action === "enable"),
    onSuccess: (data, { pack, action }) =>
      done(
        data,
        action === "install"
          ? `${pack.name} installed.`
          : `${pack.name} ${action === "enable" ? "enabled" : "disabled"}.`,
      ),
  });
  const setPerm = useMutation({
    mutationFn: ({ pack, name, ids }: { pack: PackInfo; name: string; ids: string[] }) =>
      setupApi.setPackPermission(pack.key, name, ids),
    onSuccess: (data) => {
      qc.setQueryData(["setup", "packs"], data);
      void qc.invalidateQueries({ queryKey: ["auth"] });
      toast.show("Permission updated.");
    },
    onError: (e) => toast.show(errorMessage(e), "error"),
  });
  const staffProfiles = (profiles.data ?? []).filter((p) => !p.is_portal && !p.is_locked);

  return (
    <div>
      <PageHeader
        title="Industry Packs"
        subtitle="Versioned bundles of objects, fields, apps, profiles, reports and business rules for an industry."
        icon={<PackageIcon size={22} className="text-brand-700" />}
      />
      {packs.isPending ? (
        <Spinner label="Loading packs" />
      ) : packs.isError ? (
        <Alert tone="error">{errorMessage(packs.error)}</Alert>
      ) : packs.data.length === 0 ? (
        <EmptyState
          title="No packs available"
          description="Industry packs shipped with this version appear here."
        />
      ) : (
        <div className="space-y-4">
          {packs.data.map((p) => (
            <section key={p.key} className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="flex items-center gap-2 text-lg font-semibold text-slate-900">
                    {p.name}
                    <Badge>v{p.version}</Badge>
                    {p.installed_version ? (
                      p.is_enabled ? (
                        <Badge tone="green">Enabled</Badge>
                      ) : (
                        <Badge tone="amber">Disabled</Badge>
                      )
                    ) : (
                      <Badge>Not installed</Badge>
                    )}
                    {p.upgrade_available && <Badge tone="blue">Upgrade available</Badge>}
                  </h2>
                  <p className="mt-1 max-w-3xl text-sm text-slate-600">{p.description}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    Region: {p.region} •{" "}
                    {Object.entries(p.contents)
                      .filter(([, n]) => n > 0)
                      .map(([k, n]) => contentLabel(k, n))
                      .join(", ")}
                    {p.installed_at && ` • Installed ${formatDateTimeValue(p.installed_at)}`}
                  </p>
                </div>
                {canManage && (
                  <div className="flex gap-2">
                    {(!p.installed_version || p.upgrade_available) && (
                      <Button onClick={() => setConfirm({ pack: p, action: "install" })}>
                        {p.installed_version ? "Upgrade" : "Install"}
                      </Button>
                    )}
                    {p.installed_version && (
                      <Button
                        variant="secondary"
                        onClick={() => setConfirm({ pack: p, action: p.is_enabled ? "disable" : "enable" })}
                      >
                        {p.is_enabled ? "Disable" : "Enable"}
                      </Button>
                    )}
                  </div>
                )}
              </div>
              {p.installed_version && p.custom_permissions.length > 0 && (
                <div className="mt-4 border-t border-slate-100 pt-3">
                  <h3 className="text-sm font-semibold text-slate-900">Custom permissions</h3>
                  <p className="text-xs text-slate-500">
                    System Administrator always holds every permission.
                  </p>
                  {p.custom_permissions.map((cp) => (
                    <div key={cp.name} className="mt-2">
                      <p className="text-sm font-medium text-slate-800">{cp.label}</p>
                      <div className="mt-1 grid gap-1 sm:grid-cols-3">
                        {staffProfiles.map((pr) => (
                          <Checkbox
                            key={pr.id}
                            label={pr.name}
                            disabled={!canManage || setPerm.isPending}
                            checked={cp.profile_ids.includes(pr.id)}
                            onChange={(e) =>
                              setPerm.mutate({
                                pack: p,
                                name: cp.name,
                                ids: e.target.checked
                                  ? [...cp.profile_ids, pr.id]
                                  : cp.profile_ids.filter((x) => x !== pr.id),
                              })
                            }
                          />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          ))}
        </div>
      )}
      <ConfirmDialog
        open={confirm !== null}
        title={
          confirm
            ? confirm.action === "install"
              ? `${confirm.pack.installed_version ? "Upgrade" : "Install"} ${confirm.pack.name}?`
              : `${confirm.action === "enable" ? "Enable" : "Disable"} ${confirm.pack.name}?`
            : ""
        }
        confirmLabel={confirm?.action === "disable" ? "Disable" : "Continue"}
        tone={confirm?.action === "disable" ? "danger" : "primary"}
        loading={act.isPending}
        onCancel={() => setConfirm(null)}
        onConfirm={() => confirm && act.mutate(confirm)}
      >
        {act.isError && (
          <Alert tone="error" className="mb-2">
            {errorMessage(act.error)}
          </Alert>
        )}
        {confirm?.action === "install"
          ? "Adds the pack's objects, fields, apps, profiles and reports. Existing data and your customisations are kept."
          : confirm?.action === "disable"
            ? "Hides the pack's apps, objects and actions from everyone. Data is kept and returns when you enable the pack again."
            : "Makes the pack's apps, objects and actions available again."}
      </ConfirmDialog>
    </div>
  );
}

// ================================================================ portal users

export function PortalUsersPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const users = useQuery({
    queryKey: ["setup", "portal-users"],
    queryFn: ({ signal }) => setupApi.portalUsers(signal),
  });
  const [inviting, setInviting] = useState(false);
  const [contact, setContact] = useState<{ id: string; name: string } | null>(null);
  const [toggle, setToggle] = useState<PortalUser | null>(null);
  const invite = useMutation({
    mutationFn: () => setupApi.invitePortalUser(contact!.id),
    onSuccess: (u) => {
      void qc.invalidateQueries({ queryKey: ["setup", "portal-users"] });
      toast.show(`Invitation sent to ${u.email}.`);
      setInviting(false);
      setContact(null);
    },
  });
  const setActive = useMutation({
    mutationFn: (u: PortalUser) => setupApi.setPortalUserActive(u.id, !u.is_active),
    onSuccess: (u) => {
      void qc.invalidateQueries({ queryKey: ["setup", "portal-users"] });
      toast.show(`${u.name} ${u.is_active ? "activated" : "deactivated"}.`);
      setToggle(null);
    },
  });
  return (
    <div>
      <PageHeader
        title="Portal Users"
        subtitle="Customers who can sign in to the customer portal. Invite them from their contact record."
        icon={<UsersIcon size={22} className="text-brand-700" />}
        actions={
          <Button onClick={() => setInviting(true)}>
            <PlusIcon size={16} /> Invite contact
          </Button>
        }
      />
      {users.isPending ? (
        <Spinner label="Loading portal users" />
      ) : users.isError ? (
        <Alert tone="error">{errorMessage(users.error)}</Alert>
      ) : users.data.length === 0 ? (
        <EmptyState
          title="No portal users yet"
          description="Invite a contact to give them access to their cases and invoices."
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-300 bg-white">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-600">
                <th className="px-4 py-2">Name</th>
                <th className="px-4 py-2">E-mail</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Last sign-in</th>
                <th className="px-4 py-2">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {users.data.map((u) => (
                <tr key={u.id}>
                  <td className="px-4 py-2 font-medium">
                    {u.contact_id ? (
                      <Link to={`/o/contact/${u.contact_id}`} className="text-brand-700 hover:underline">
                        {u.name}
                      </Link>
                    ) : (
                      u.name
                    )}
                  </td>
                  <td className="px-4 py-2">{u.email}</td>
                  <td className="px-4 py-2">
                    {!u.is_active ? (
                      <Badge>Inactive</Badge>
                    ) : u.has_password ? (
                      <Badge tone="green">Active</Badge>
                    ) : (
                      <Badge tone="amber">Invited</Badge>
                    )}
                  </td>
                  <td className="px-4 py-2 text-slate-600">
                    {u.last_login_at ? formatDateTimeValue(u.last_login_at) : "—"}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <button
                      type="button"
                      className="text-sm font-medium text-brand-700 hover:underline"
                      onClick={() => setToggle(u)}
                    >
                      {u.is_active ? "Deactivate" : "Activate"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Modal
        open={inviting}
        onClose={() => setInviting(false)}
        size="sm"
        title="Invite a contact to the portal"
        busy={invite.isPending}
        footer={
          <>
            <Button variant="secondary" onClick={() => setInviting(false)}>
              Cancel
            </Button>
            <Button onClick={() => invite.mutate()} loading={invite.isPending} disabled={!contact}>
              Send invitation
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          {invite.isError && <Alert tone="error">{errorMessage(invite.error)}</Alert>}
          <FormField label="Contact" required hint="The contact needs an e-mail address.">
            {({ id }) => (
              <Combobox
                id={id}
                value={contact?.id ?? null}
                displayName={contact?.name}
                queryKey={["lookup", "contact"]}
                search={(q, signal) => recordsApi.lookup("contact", q, signal)}
                placeholder="Search contacts…"
                onChange={(cid, name) => setContact(cid && name ? { id: cid, name } : null)}
              />
            )}
          </FormField>
        </div>
      </Modal>
      <ConfirmDialog
        open={toggle !== null}
        title={toggle?.is_active ? `Deactivate ${toggle.name}?` : `Activate ${toggle?.name ?? ""}?`}
        tone={toggle?.is_active ? "danger" : "primary"}
        confirmLabel={toggle?.is_active ? "Deactivate" : "Activate"}
        loading={setActive.isPending}
        onCancel={() => setToggle(null)}
        onConfirm={() => toggle && setActive.mutate(toggle)}
      >
        {setActive.isError && (
          <Alert tone="error" className="mb-2">
            {errorMessage(setActive.error)}
          </Alert>
        )}
        {toggle?.is_active
          ? "They are signed out and can no longer use the portal."
          : "They can sign in to the portal again."}
      </ConfirmDialog>
    </div>
  );
}

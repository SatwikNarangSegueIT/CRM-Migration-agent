import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { errorMessage } from "../../api/client";
import { setupApi, type ProfileDetail, type RoleInfo } from "../../api/setup";
import type { ObjectAccess } from "../../api/types";
import { useAuth } from "../../auth/context";
import { controlClass } from "../../components/record/FieldInput";
import { LockIcon, PlusIcon, ShieldIcon, TrashIcon } from "../../components/icons";
import {
  Alert,
  Badge,
  Button,
  Card,
  ConfirmDialog,
  FormField,
  Input,
  PageHeader,
  Spinner,
  useToast,
} from "../../components/ui";
import { cx } from "../../components/ui/cx";
import { Modal } from "../../components/ui/Modal";
import { useObjectMeta, useObjects } from "../../lib/records";

export function useCanManageSecurity() {
  return useAuth().can("manage_profiles_sharing");
}

export function ProfilesPage() {
  const manage = useCanManageSecurity();
  const navigate = useNavigate();
  const profiles = useQuery({
    queryKey: ["setup", "profiles"],
    queryFn: ({ signal }) => setupApi.profiles(signal),
  });
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [cloneFrom, setCloneFrom] = useState("");
  const create = useMutation({
    mutationFn: () => setupApi.createProfile({ name, clone_from_id: cloneFrom || null }),
    onSuccess: (p) => navigate(`/setup/profiles/${p.id}`),
  });
  return (
    <div>
      <PageHeader
        title="Profiles"
        subtitle="What users can do: system permissions, object permissions and field-level security."
        icon={<ShieldIcon size={22} className="text-brand-700" />}
        actions={
          manage && (
            <Button onClick={() => setCreating(true)}>
              <PlusIcon size={16} /> New Profile
            </Button>
          )
        }
      />
      {profiles.isPending ? (
        <Spinner label="Loading" />
      ) : profiles.isError ? (
        <Alert tone="error">{errorMessage(profiles.error)}</Alert>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-300 bg-white">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-600">
                <th className="px-4 py-2">Profile</th>
                <th className="px-4 py-2">Description</th>
                <th className="px-4 py-2">Type</th>
                <th className="px-4 py-2">Users</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {profiles.data.map((p) => (
                <tr key={p.id}>
                  <td className="px-4 py-2">
                    <Link
                      to={`/setup/profiles/${p.id}`}
                      className="font-medium text-brand-700 hover:underline"
                    >
                      {p.name}
                    </Link>{" "}
                    {p.is_locked && (
                      <LockIcon size={14} className="inline text-slate-400" aria-label="Locked" />
                    )}
                  </td>
                  <td className="max-w-lg px-4 py-2 text-slate-600">{p.description}</td>
                  <td className="px-4 py-2">
                    {p.is_portal ? <Badge tone="purple">Portal</Badge> : <Badge>Staff</Badge>}
                  </td>
                  <td className="px-4 py-2">{p.user_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Modal
        open={creating}
        onClose={() => setCreating(false)}
        title="New profile"
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreating(false)}>
              Cancel
            </Button>
            <Button onClick={() => create.mutate()} loading={create.isPending} disabled={!name.trim()}>
              Create
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          {create.isError && <Alert tone="error">{errorMessage(create.error)}</Alert>}
          <FormField label="Name" required>
            {({ id }) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} />}
          </FormField>
          <FormField label="Copy permissions from" hint="Start from an existing profile (recommended).">
            {({ id }) => (
              <select
                id={id}
                className={controlClass(false)}
                value={cloneFrom}
                onChange={(e) => setCloneFrom(e.target.value)}
              >
                <option value="">Nothing (no access)</option>
                {profiles.data
                  ?.filter((p) => !p.is_portal)
                  .map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
              </select>
            )}
          </FormField>
        </div>
      </Modal>
    </div>
  );
}

const FLAGS: { key: keyof ObjectAccess; label: string; title: string }[] = [
  { key: "read", label: "R", title: "Read" },
  { key: "create", label: "C", title: "Create" },
  { key: "edit", label: "E", title: "Edit" },
  { key: "delete", label: "D", title: "Delete" },
  { key: "view_all", label: "VA", title: "View All" },
  { key: "modify_all", label: "MA", title: "Modify All" },
];

function normalise(a: ObjectAccess, changed: keyof ObjectAccess): ObjectAccess {
  const n = { ...a };
  if (changed === "read" && !n.read)
    return { read: false, create: false, edit: false, delete: false, view_all: false, modify_all: false };
  if (n[changed] && changed !== "read") n.read = true;
  if (changed === "modify_all" && n.modify_all) {
    n.view_all = true;
    n.edit = true;
  }
  if ((changed === "view_all" || changed === "edit") && !n[changed]) n.modify_all = false;
  return n;
}

export function ProfileDetailPage() {
  const { id = "" } = useParams();
  const manage = useCanManageSecurity();
  const toast = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const profile = useQuery({
    queryKey: ["setup", "profile", id],
    queryFn: ({ signal }) => setupApi.profile(id, signal),
  });
  const catalog = useQuery({
    queryKey: ["setup", "catalog"],
    queryFn: ({ signal }) => setupApi.catalog(signal),
    staleTime: Infinity,
  });
  const objects = useObjects();
  const [tab, setTab] = useState<"system" | "objects" | "fields">("objects");
  const [deleting, setDeleting] = useState(false);
  const onSaved = (p: ProfileDetail) => {
    queryClient.setQueryData(["setup", "profile", id], p);
    void queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
    toast.show("Profile saved.");
  };
  const remove = useMutation({
    mutationFn: () => setupApi.deleteProfile(id),
    onSuccess: () => navigate("/setup/profiles"),
    onError: (e) => {
      setDeleting(false);
      toast.show(errorMessage(e), "error");
    },
  });
  if (profile.isPending) return <Spinner label="Loading" />;
  if (profile.isError) return <Alert tone="error">{errorMessage(profile.error)}</Alert>;
  const p = profile.data;
  const editable = manage && !p.is_locked;
  return (
    <div className="space-y-3">
      <PageHeader
        title={p.name}
        subtitle={p.description}
        breadcrumbs={[{ label: "Profiles", to: "/setup/profiles" }, { label: p.name }]}
        icon={<ShieldIcon size={22} className="text-brand-700" />}
        actions={
          editable &&
          p.user_count === 0 && (
            <Button variant="danger" onClick={() => setDeleting(true)}>
              Delete
            </Button>
          )
        }
      />
      {p.is_locked && (
        <Alert tone="info">The System Administrator profile has every permission and can't be edited.</Alert>
      )}
      <div role="tablist" className="flex gap-1 border-b border-slate-200">
        {(["objects", "fields", "system"] as const).map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            type="button"
            className={cx(
              "border-b-[3px] px-3 py-2 text-sm",
              tab === t ? "border-brand-700 font-semibold" : "border-transparent text-slate-600",
            )}
            onClick={() => setTab(t)}
          >
            {
              { objects: "Object Permissions", fields: "Field-Level Security", system: "System Permissions" }[
                t
              ]
            }
          </button>
        ))}
      </div>
      {tab === "system" && catalog.data && (
        <SystemPermissions
          profile={p}
          catalog={catalog.data.system_permissions}
          editable={editable}
          onSaved={onSaved}
        />
      )}
      {tab === "objects" && objects.data && (
        <ObjectPermissions
          profile={p}
          objects={[
            ...objects.data.map((o) => ({ api: o.api_name, label: o.plural_label })),
            { api: "report", label: "Reports" },
            { api: "dashboard", label: "Dashboards" },
          ]}
          editable={editable}
          onSaved={onSaved}
        />
      )}
      {tab === "fields" && objects.data && (
        <FieldPermissions
          profile={p}
          objects={objects.data.map((o) => ({ api: o.api_name, label: o.label }))}
          editable={editable}
          onSaved={onSaved}
        />
      )}
      <ConfirmDialog
        open={deleting}
        title="Delete profile?"
        tone="danger"
        confirmLabel="Delete"
        loading={remove.isPending}
        onCancel={() => setDeleting(false)}
        onConfirm={() => remove.mutate()}
      />
    </div>
  );
}

function SystemPermissions({
  profile,
  catalog,
  editable,
  onSaved,
}: {
  profile: ProfileDetail;
  catalog: { value: string; label: string }[];
  editable: boolean;
  onSaved: (p: ProfileDetail) => void;
}) {
  const [selected, setSelected] = useState(new Set(profile.system_permissions));
  const save = useMutation({
    mutationFn: () => setupApi.setSystemPermissions(profile.id, [...selected]),
    onSuccess: onSaved,
  });
  return (
    <Card>
      {save.isError && (
        <Alert tone="error" className="mb-3">
          {errorMessage(save.error)}
        </Alert>
      )}
      <ul className="grid gap-2 sm:grid-cols-2">
        {catalog.map((c) => (
          <li key={c.value}>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                disabled={!editable}
                checked={selected.has(c.value)}
                onChange={(e) => {
                  const n = new Set(selected);
                  if (e.target.checked) n.add(c.value);
                  else n.delete(c.value);
                  setSelected(n);
                }}
              />
              {c.label}
            </label>
          </li>
        ))}
      </ul>
      {editable && (
        <Button className="mt-4" onClick={() => save.mutate()} loading={save.isPending}>
          Save system permissions
        </Button>
      )}
    </Card>
  );
}

function ObjectPermissions({
  profile,
  objects,
  editable,
  onSaved,
}: {
  profile: ProfileDetail;
  objects: { api: string; label: string }[];
  editable: boolean;
  onSaved: (p: ProfileDetail) => void;
}) {
  const initial = useMemo(
    () => Object.fromEntries(profile.object_permissions.map((o) => [o.object_api_name, o as ObjectAccess])),
    [profile],
  );
  const [perms, setPerms] = useState<Record<string, ObjectAccess>>(initial);
  const empty: ObjectAccess = {
    read: false,
    create: false,
    edit: false,
    delete: false,
    view_all: false,
    modify_all: false,
  };
  const changed = objects.filter(
    (o) => JSON.stringify(perms[o.api] ?? empty) !== JSON.stringify(initial[o.api] ?? empty),
  );
  const save = useMutation({
    mutationFn: () =>
      setupApi.setObjectPermissions(
        profile.id,
        Object.fromEntries(changed.map((o) => [o.api, perms[o.api] ?? empty])),
      ),
    onSuccess: onSaved,
  });
  return (
    <Card>
      {save.isError && (
        <Alert tone="error" className="mb-3">
          {errorMessage(save.error)}
        </Alert>
      )}
      <div className="max-h-[65vh] overflow-auto">
        <table className="min-w-full text-sm">
          <thead className="sticky top-0 bg-white">
            <tr className="text-left text-xs text-slate-600">
              <th className="px-3 py-2">Object</th>
              {FLAGS.map((f) => (
                <th key={f.key} className="px-2 py-2 text-center" title={f.title}>
                  <abbr title={f.title}>{f.label}</abbr>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {objects.map((o) => {
              const a = perms[o.api] ?? empty;
              return (
                <tr key={o.api}>
                  <td className="px-3 py-1.5">{o.label}</td>
                  {FLAGS.map((f) => (
                    <td key={f.key} className="px-2 py-1.5 text-center">
                      <input
                        type="checkbox"
                        aria-label={`${o.label}: ${f.title}`}
                        disabled={!editable}
                        checked={a[f.key]}
                        onChange={() =>
                          setPerms({ ...perms, [o.api]: normalise({ ...a, [f.key]: !a[f.key] }, f.key) })
                        }
                      />
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {editable && (
        <Button
          className="mt-4"
          disabled={changed.length === 0}
          onClick={() => save.mutate()}
          loading={save.isPending}
        >
          Save {changed.length ? `(${changed.length} changed)` : ""}
        </Button>
      )}
      <p className="mt-2 text-xs text-slate-500">
        View All reads every record regardless of sharing; Modify All edits (and, with Delete, deletes) every
        record. Changes are audited.
      </p>
    </Card>
  );
}

function FieldPermissions({
  profile,
  objects,
  editable,
  onSaved,
}: {
  profile: ProfileDetail;
  objects: { api: string; label: string }[];
  editable: boolean;
  onSaved: (p: ProfileDetail) => void;
}) {
  const [object, setObject] = useState(objects[0]?.api ?? "account");
  const meta = useObjectMeta(object);
  const overrides = useMemo(
    () =>
      Object.fromEntries(
        profile.field_permissions
          .filter((f) => f.object_api_name === object)
          .map((f) => [f.field_api_name, f.access]),
      ),
    [profile, object],
  );
  const [changes, setChanges] = useState<Record<string, "hidden" | "read" | "edit" | null>>({});
  const save = useMutation({
    mutationFn: () =>
      setupApi.setFieldPermissions(
        profile.id,
        Object.entries(changes).map(([field, access]) => ({
          object_api_name: object,
          field_api_name: field,
          access,
        })),
      ),
    onSuccess: (p) => {
      setChanges({});
      onSaved(p);
    },
  });
  const fields = Object.values(meta.data?.fields ?? {}).filter((f) => !f.is_system || f.api_name === "name");
  return (
    <Card>
      <div className="mb-3 flex items-center gap-2">
        <label htmlFor="fls-object" className="text-sm font-medium">
          Object
        </label>
        <select
          id="fls-object"
          className={controlClass(false, "w-64")}
          value={object}
          onChange={(e) => {
            setObject(e.target.value);
            setChanges({});
          }}
        >
          {objects.map((o) => (
            <option key={o.api} value={o.api}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
      {save.isError && (
        <Alert tone="error" className="mb-3">
          {errorMessage(save.error)}
        </Alert>
      )}
      {meta.isPending ? (
        <Spinner label="Loading" />
      ) : (
        <table className="min-w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-slate-600">
              <th className="px-3 py-2">Field</th>
              <th className="px-3 py-2">Default</th>
              <th className="px-3 py-2">Access for this profile</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {fields.map((f) => {
              const value = f.api_name in changes ? changes[f.api_name] : (overrides[f.api_name] ?? null);
              return (
                <tr key={f.api_name}>
                  <td className="px-3 py-1.5">
                    {f.label}
                    {f.is_custom && <Badge tone="blue">custom</Badge>}
                  </td>
                  <td className="px-3 py-1.5 text-slate-500">{f.default_access}</td>
                  <td className="px-3 py-1.5">
                    <select
                      aria-label={`Access to ${f.label}`}
                      disabled={!editable}
                      className={controlClass(false, "w-48 py-1")}
                      value={value ?? ""}
                      onChange={(e) =>
                        setChanges({ ...changes, [f.api_name]: (e.target.value || null) as "edit" | null })
                      }
                    >
                      <option value="">Default ({f.default_access})</option>
                      <option value="edit">Read & edit</option>
                      <option value="read">Read only</option>
                      <option value="hidden">Hidden</option>
                    </select>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      {editable && (
        <Button
          className="mt-4"
          disabled={Object.keys(changes).length === 0}
          onClick={() => save.mutate()}
          loading={save.isPending}
        >
          Save field access
        </Button>
      )}
    </Card>
  );
}

export function RolesPage() {
  const manage = useCanManageSecurity();
  const toast = useToast();
  const queryClient = useQueryClient();
  const roles = useQuery({ queryKey: ["setup", "roles"], queryFn: ({ signal }) => setupApi.roles(signal) });
  const [editing, setEditing] = useState<{ role: RoleInfo | null; parent: string | null } | null>(null);
  const [name, setName] = useState("");
  const [deleting, setDeleting] = useState<RoleInfo | null>(null);
  const save = useMutation({
    mutationFn: () =>
      editing!.role
        ? setupApi.updateRole(editing!.role.id, { name })
        : setupApi.createRole({ name, parent_id: editing!.parent }),
    onSuccess: () => {
      setEditing(null);
      void queryClient.invalidateQueries({ queryKey: ["setup", "roles"] });
      toast.show("Role saved.");
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => setupApi.deleteRole(id),
    onSuccess: () => {
      setDeleting(null);
      void queryClient.invalidateQueries({ queryKey: ["setup", "roles"] });
    },
    onError: (e) => {
      setDeleting(null);
      toast.show(errorMessage(e), "error");
    },
  });
  const children = (parent: string | null) =>
    (roles.data ?? []).filter((r) => r.parent_id === parent).sort((a, b) => a.name.localeCompare(b.name));
  const render = (parent: string | null, depth: number): React.ReactNode =>
    children(parent).map((r) => (
      <li key={r.id}>
        <div
          className="flex items-center justify-between gap-2 rounded px-2 py-1.5 hover:bg-slate-50"
          style={{ paddingLeft: depth * 20 + 8 }}
        >
          <span>
            {r.name} <span className="text-xs text-slate-500">({r.user_count} users)</span>
          </span>
          {manage && (
            <span className="flex gap-2 text-xs">
              <button
                type="button"
                className="text-brand-700 hover:underline"
                onClick={() => {
                  setName("");
                  setEditing({ role: null, parent: r.id });
                }}
              >
                Add role below
              </button>
              <button
                type="button"
                className="text-brand-700 hover:underline"
                onClick={() => {
                  setName(r.name);
                  setEditing({ role: r, parent: r.parent_id });
                }}
              >
                Rename
              </button>
              <button type="button" className="text-red-700 hover:underline" onClick={() => setDeleting(r)}>
                Delete
              </button>
            </span>
          )}
        </div>
        <ul>{render(r.id, depth + 1)}</ul>
      </li>
    ));
  return (
    <div>
      <PageHeader
        title="Role Hierarchy"
        subtitle="Managers see and edit the records owned by users in roles below them (unless an object's sharing settings turn this off)."
        actions={
          manage && (
            <Button
              onClick={() => {
                setName("");
                setEditing({ role: null, parent: null });
              }}
            >
              <PlusIcon size={16} /> New top-level role
            </Button>
          )
        }
      />
      <Card>
        {roles.isPending ? <Spinner label="Loading" /> : <ul className="text-sm">{render(null, 0)}</ul>}
      </Card>
      <Modal
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={editing?.role ? "Rename role" : "New role"}
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setEditing(null)}>
              Cancel
            </Button>
            <Button onClick={() => save.mutate()} loading={save.isPending} disabled={!name.trim()}>
              Save
            </Button>
          </>
        }
      >
        {save.isError && (
          <Alert tone="error" className="mb-3">
            {errorMessage(save.error)}
          </Alert>
        )}
        <FormField label="Role name" required>
          {({ id }) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} />}
        </FormField>
      </Modal>
      <ConfirmDialog
        open={deleting !== null}
        title={`Delete role ${deleting?.name}?`}
        tone="danger"
        confirmLabel="Delete"
        loading={remove.isPending}
        onCancel={() => setDeleting(null)}
        onConfirm={() => deleting && remove.mutate(deleting.id)}
      >
        Roles with users or child roles can't be deleted.
      </ConfirmDialog>
    </div>
  );
}

export { TrashIcon };

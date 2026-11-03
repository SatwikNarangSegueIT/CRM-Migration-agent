import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { errorMessage } from "../../api/client";
import { metaApi } from "../../api/records";
import { setupApi, type Group, type Queue, type SharingRule } from "../../api/setup";
import { controlClass } from "../../components/record/FieldInput";
import { PlusIcon, TrashIcon } from "../../components/icons";
import {
  Alert,
  Badge,
  Button,
  Card,
  FormField,
  Input,
  PageHeader,
  Spinner,
  useToast,
} from "../../components/ui";
import { Modal } from "../../components/ui/Modal";
import { useObjects } from "../../lib/records";
import { useCanManageSecurity } from "./SecurityPages";

const ACCESS_LABEL: Record<string, string> = {
  private: "Private",
  read: "Public Read Only",
  read_write: "Public Read/Write",
  controlled_by_parent: "Controlled by Parent",
};

export function SharingPage() {
  const manage = useCanManageSecurity();
  const toast = useToast();
  const queryClient = useQueryClient();
  const objects = useObjects();
  const defaults = useQuery({
    queryKey: ["setup", "owd"],
    queryFn: ({ signal }) => setupApi.sharingDefaults(signal),
  });
  const rules = useQuery({
    queryKey: ["setup", "rules"],
    queryFn: ({ signal }) => setupApi.sharingRules(undefined, signal),
  });
  const roles = useQuery({ queryKey: ["setup", "roles"], queryFn: ({ signal }) => setupApi.roles(signal) });
  const groups = useQuery({
    queryKey: ["setup", "groups"],
    queryFn: ({ signal }) => setupApi.groups(signal),
  });
  const [editingRule, setEditingRule] = useState<Partial<SharingRule> | null>(null);
  const setOwd = useMutation({
    mutationFn: (v: { api: string; access: string; hierarchy: boolean }) =>
      setupApi.setSharingDefault(v.api, { access: v.access, grant_access_using_hierarchy: v.hierarchy }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["setup", "owd"] });
      toast.show("Organisation-wide default saved.");
    },
    onError: (e) => toast.show(errorMessage(e), "error"),
  });
  const deleteRule = useMutation({
    mutationFn: (id: string) => setupApi.deleteSharingRule(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["setup", "rules"] }),
  });
  const label = (api: string) => objects.data?.find((o) => o.api_name === api)?.plural_label ?? api;
  const principal = (type: string | null, id: string | null) => {
    if (!type || !id) return "";
    if (type === "group") return `Group: ${groups.data?.find((g) => g.id === id)?.name ?? id}`;
    const role = roles.data?.find((r) => r.id === id)?.name ?? id;
    return type === "role_and_subordinates"
      ? `Role & subordinates: ${role}`
      : type === "queue"
        ? "Queue"
        : `Role: ${role}`;
  };
  return (
    <div className="space-y-4">
      <PageHeader
        title="Sharing Settings"
        subtitle="Organisation-wide defaults set the baseline record access; sharing rules open access up for roles and groups."
      />
      <Card>
        <h2 className="mb-2 font-semibold text-slate-900">Organisation-wide defaults</h2>
        {defaults.isPending ? (
          <Spinner label="Loading" />
        ) : (
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-600">
                <th className="px-3 py-2">Object</th>
                <th className="px-3 py-2">Default access</th>
                <th className="px-3 py-2">Grant access using hierarchies</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(defaults.data ?? [])
                .filter(
                  (d) =>
                    objects.data?.some((o) => o.api_name === d.object_api_name) ||
                    ["report", "dashboard"].includes(d.object_api_name),
                )
                .map((d) => (
                  <tr key={d.object_api_name}>
                    <td className="px-3 py-1.5">{label(d.object_api_name)}</td>
                    <td className="px-3 py-1.5">
                      {d.access === "controlled_by_parent" || !manage ? (
                        ACCESS_LABEL[d.access]
                      ) : (
                        <select
                          aria-label={`Default access for ${label(d.object_api_name)}`}
                          className={controlClass(false, "w-48 py-1")}
                          value={d.access}
                          onChange={(e) =>
                            setOwd.mutate({
                              api: d.object_api_name,
                              access: e.target.value,
                              hierarchy: d.grant_access_using_hierarchy,
                            })
                          }
                        >
                          <option value="private">Private</option>
                          <option value="read">Public Read Only</option>
                          <option value="read_write">Public Read/Write</option>
                        </select>
                      )}
                    </td>
                    <td className="px-3 py-1.5">
                      <input
                        type="checkbox"
                        aria-label="Grant access using hierarchies"
                        disabled={!manage || d.access === "controlled_by_parent"}
                        checked={d.grant_access_using_hierarchy}
                        onChange={(e) =>
                          setOwd.mutate({
                            api: d.object_api_name,
                            access: d.access,
                            hierarchy: e.target.checked,
                          })
                        }
                      />
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        )}
      </Card>
      <Card>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="font-semibold text-slate-900">Sharing rules</h2>
          {manage && (
            <Button
              size="sm"
              onClick={() =>
                setEditingRule({
                  rule_type: "owner",
                  source_type: "role",
                  target_type: "role",
                  access: "read",
                  object_api_name: "lead",
                })
              }
            >
              <PlusIcon size={14} /> New rule
            </Button>
          )}
        </div>
        {rules.isPending ? (
          <Spinner label="Loading" />
        ) : (rules.data ?? []).length === 0 ? (
          <p className="text-sm text-slate-500">No sharing rules.</p>
        ) : (
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-600">
                <th className="px-3 py-2">Rule</th>
                <th className="px-3 py-2">Object</th>
                <th className="px-3 py-2">Shares records</th>
                <th className="px-3 py-2">With</th>
                <th className="px-3 py-2">Access</th>
                <th />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rules.data!.map((r) => (
                <tr key={r.id}>
                  <td className="px-3 py-1.5">
                    <button
                      type="button"
                      className="text-brand-700 hover:underline"
                      onClick={() => setEditingRule(r)}
                      disabled={!manage}
                    >
                      {r.name}
                    </button>
                  </td>
                  <td className="px-3 py-1.5">{label(r.object_api_name)}</td>
                  <td className="px-3 py-1.5">
                    {r.rule_type === "owner"
                      ? `owned by ${principal(r.source_type, r.source_id)}`
                      : `matching ${r.criteria?.conditions.length ?? 0} condition(s)`}
                  </td>
                  <td className="px-3 py-1.5">{principal(r.target_type, r.target_id)}</td>
                  <td className="px-3 py-1.5">
                    <Badge tone={r.access === "read" ? "gray" : "amber"}>
                      {r.access === "read" ? "Read only" : "Read/Write"}
                    </Badge>
                  </td>
                  <td className="px-3 py-1.5 text-right">
                    {manage && (
                      <button
                        type="button"
                        aria-label={`Delete ${r.name}`}
                        className="rounded p-1 hover:bg-slate-100"
                        onClick={() => deleteRule.mutate(r.id)}
                      >
                        <TrashIcon size={14} />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      {editingRule && <RuleEditor rule={editingRule} onClose={() => setEditingRule(null)} />}
    </div>
  );
}

function RuleEditor({ rule, onClose }: { rule: Partial<SharingRule>; onClose: () => void }) {
  const queryClient = useQueryClient();
  const objects = useObjects();
  const roles = useQuery({ queryKey: ["setup", "roles"], queryFn: ({ signal }) => setupApi.roles(signal) });
  const groups = useQuery({
    queryKey: ["setup", "groups"],
    queryFn: ({ signal }) => setupApi.groups(signal),
  });
  const [r, setR] = useState<Partial<SharingRule>>(rule);
  const [criteriaText, setCriteriaText] = useState(
    rule.criteria
      ? JSON.stringify(rule.criteria)
      : '{"logic":"and","conditions":[{"field":"status","op":"eq","value":"New"}]}',
  );
  const save = useMutation({
    mutationFn: () => {
      const body = {
        ...r,
        criteria: r.rule_type === "criteria" ? JSON.parse(criteriaText) : null,
        source_type: r.rule_type === "owner" ? r.source_type : null,
        source_id: r.rule_type === "owner" ? r.source_id : null,
      } as Omit<SharingRule, "id">;
      return setupApi.saveSharingRule(rule.id ?? null, body);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["setup", "rules"] });
      onClose();
    },
  });
  const principalOptions = (type?: string | null) =>
    type === "group"
      ? (groups.data ?? []).map((g) => ({ id: g.id, name: g.name }))
      : (roles.data ?? []).map((x) => ({ id: x.id, name: x.name }));
  return (
    <Modal
      open
      onClose={onClose}
      title={rule.id ? "Edit sharing rule" : "New sharing rule"}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => save.mutate()}
            loading={save.isPending}
            disabled={!r.name || !r.target_id || (r.rule_type === "owner" && !r.source_id)}
          >
            Save
          </Button>
        </>
      }
    >
      <div className="grid gap-3 sm:grid-cols-2">
        {save.isError && (
          <div className="sm:col-span-2">
            <Alert tone="error">{errorMessage(save.error)}</Alert>
          </div>
        )}
        <FormField label="Rule name" required>
          {({ id }) => (
            <Input id={id} value={r.name ?? ""} onChange={(e) => setR({ ...r, name: e.target.value })} />
          )}
        </FormField>
        <FormField label="Object">
          {({ id }) => (
            <select
              id={id}
              className={controlClass(false)}
              value={r.object_api_name}
              onChange={(e) => setR({ ...r, object_api_name: e.target.value })}
            >
              {(objects.data ?? [])
                .filter((o) => !o.is_detail_only)
                .map((o) => (
                  <option key={o.api_name} value={o.api_name}>
                    {o.plural_label}
                  </option>
                ))}
            </select>
          )}
        </FormField>
        <FormField label="Rule type">
          {({ id }) => (
            <select
              id={id}
              className={controlClass(false)}
              value={r.rule_type}
              onChange={(e) => setR({ ...r, rule_type: e.target.value as "owner" })}
            >
              <option value="owner">Based on record owner</option>
              <option value="criteria">Based on criteria</option>
            </select>
          )}
        </FormField>
        <FormField label="Access">
          {({ id }) => (
            <select
              id={id}
              className={controlClass(false)}
              value={r.access}
              onChange={(e) => setR({ ...r, access: e.target.value as "read" })}
            >
              <option value="read">Read only</option>
              <option value="read_write">Read/Write</option>
            </select>
          )}
        </FormField>
        {r.rule_type === "owner" ? (
          <>
            <FormField label="Records owned by">
              {({ id }) => (
                <select
                  id={id}
                  className={controlClass(false)}
                  value={r.source_type ?? "role"}
                  onChange={(e) => setR({ ...r, source_type: e.target.value, source_id: null })}
                >
                  <option value="role">Role</option>
                  <option value="role_and_subordinates">Role and subordinates</option>
                  <option value="group">Public group</option>
                </select>
              )}
            </FormField>
            <FormField label="Which one">
              {({ id }) => (
                <select
                  id={id}
                  className={controlClass(false)}
                  value={r.source_id ?? ""}
                  onChange={(e) => setR({ ...r, source_id: e.target.value })}
                >
                  <option value="">Choose…</option>
                  {principalOptions(r.source_type).map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.name}
                    </option>
                  ))}
                </select>
              )}
            </FormField>
          </>
        ) : (
          <div className="sm:col-span-2">
            <FormField
              label="Criteria (JSON)"
              hint='e.g. {"logic":"and","conditions":[{"field":"status","op":"eq","value":"New"}]}'
            >
              {({ id }) => (
                <textarea
                  id={id}
                  rows={3}
                  className={controlClass(false, "font-mono text-xs")}
                  value={criteriaText}
                  onChange={(e) => setCriteriaText(e.target.value)}
                />
              )}
            </FormField>
          </div>
        )}
        <FormField label="Share with">
          {({ id }) => (
            <select
              id={id}
              className={controlClass(false)}
              value={r.target_type}
              onChange={(e) => setR({ ...r, target_type: e.target.value, target_id: undefined })}
            >
              <option value="role">Role</option>
              <option value="role_and_subordinates">Role and subordinates</option>
              <option value="group">Public group</option>
            </select>
          )}
        </FormField>
        <FormField label="Which one">
          {({ id }) => (
            <select
              id={id}
              className={controlClass(false)}
              value={r.target_id ?? ""}
              onChange={(e) => setR({ ...r, target_id: e.target.value })}
            >
              <option value="">Choose…</option>
              {principalOptions(r.target_type).map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </select>
          )}
        </FormField>
      </div>
    </Modal>
  );
}

export function GroupsQueuesPage() {
  const manage = useCanManageSecurity();
  const queryClient = useQueryClient();
  const toast = useToast();
  const groups = useQuery({
    queryKey: ["setup", "groups"],
    queryFn: ({ signal }) => setupApi.groups(signal),
  });
  const queues = useQuery({
    queryKey: ["setup", "queues"],
    queryFn: ({ signal }) => setupApi.queues(signal),
  });
  const users = useQuery({
    queryKey: ["user-picker", "all-200"],
    queryFn: ({ signal }) => metaApi.users("", signal),
  });
  const objects = useObjects();
  const [editingGroup, setEditingGroup] = useState<Group | "new" | null>(null);
  const [editingQueue, setEditingQueue] = useState<Queue | "new" | null>(null);
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["setup", "groups"] });
    void queryClient.invalidateQueries({ queryKey: ["setup", "queues"] });
  };
  const removeGroup = useMutation({
    mutationFn: setupApi.deleteGroup,
    onSuccess: refresh,
    onError: (e) => toast.show(errorMessage(e), "error"),
  });
  const removeQueue = useMutation({
    mutationFn: setupApi.deleteQueue,
    onSuccess: refresh,
    onError: (e) => toast.show(errorMessage(e), "error"),
  });
  const userName = (id: string) => users.data?.find((u) => u.id === id)?.name ?? "User";
  return (
    <div className="space-y-4">
      <PageHeader
        title="Public Groups & Queues"
        subtitle="Groups are used by sharing rules; queues own cases and leads until a member accepts them."
      />
      <Card>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="font-semibold">Public groups</h2>
          {manage && (
            <Button size="sm" onClick={() => setEditingGroup("new")}>
              <PlusIcon size={14} /> New group
            </Button>
          )}
        </div>
        {(groups.data ?? []).length === 0 ? (
          <p className="text-sm text-slate-500">No groups.</p>
        ) : (
          <ul className="divide-y divide-slate-100 text-sm">
            {groups.data!.map((g) => (
              <li key={g.id} className="flex items-center justify-between py-2">
                <span>
                  <strong>{g.name}</strong>{" "}
                  <span className="text-slate-500">
                    · {g.user_ids.length} users, {g.roles.length} roles
                  </span>
                </span>
                {manage && (
                  <span className="flex gap-2">
                    <Button size="sm" variant="secondary" onClick={() => setEditingGroup(g)}>
                      Edit
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => removeGroup.mutate(g.id)}>
                      <TrashIcon size={14} />
                    </Button>
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="font-semibold">Queues</h2>
          {manage && (
            <Button size="sm" onClick={() => setEditingQueue("new")}>
              <PlusIcon size={14} /> New queue
            </Button>
          )}
        </div>
        <ul className="divide-y divide-slate-100 text-sm">
          {(queues.data ?? []).map((q) => (
            <li key={q.id} className="flex items-center justify-between py-2">
              <span>
                <strong>{q.name}</strong>{" "}
                <span className="text-slate-500">
                  · {q.object_api_names.join(", ")} · members: {q.user_ids.map(userName).join(", ") || "none"}
                </span>
              </span>
              {manage && (
                <span className="flex gap-2">
                  <Button size="sm" variant="secondary" onClick={() => setEditingQueue(q)}>
                    Edit
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => removeQueue.mutate(q.id)}>
                    <TrashIcon size={14} />
                  </Button>
                </span>
              )}
            </li>
          ))}
        </ul>
      </Card>
      {editingGroup && (
        <MemberEditor
          kind="group"
          item={editingGroup === "new" ? null : editingGroup}
          users={users.data ?? []}
          objects={[]}
          onClose={() => {
            setEditingGroup(null);
            refresh();
          }}
        />
      )}
      {editingQueue && (
        <MemberEditor
          kind="queue"
          item={editingQueue === "new" ? null : editingQueue}
          users={users.data ?? []}
          objects={(objects.data ?? [])
            .filter((o) => ["case", "lead"].includes(o.api_name) || o.is_custom)
            .map((o) => ({ api: o.api_name, label: o.plural_label }))}
          onClose={() => {
            setEditingQueue(null);
            refresh();
          }}
        />
      )}
    </div>
  );
}

function MemberEditor({
  kind,
  item,
  users,
  objects,
  onClose,
}: {
  kind: "group" | "queue";
  item: Group | Queue | null;
  users: { id: string; name: string }[];
  objects: { api: string; label: string }[];
  onClose: () => void;
}) {
  const [name, setName] = useState(item?.name ?? "");
  const [members, setMembers] = useState(new Set(item?.user_ids ?? []));
  const [objs, setObjs] = useState(
    new Set(item && "object_api_names" in item ? item.object_api_names : ["case"]),
  );
  const save = useMutation({
    mutationFn: async () => {
      if (kind === "group") {
        const g = await setupApi.saveGroup(item?.id ?? null, { name });
        await setupApi.setGroupMembers(g.id, {
          user_ids: [...members],
          roles: item && "roles" in item ? item.roles : [],
        });
      } else {
        const q = await setupApi.saveQueue(item?.id ?? null, { name, object_api_names: [...objs] });
        await setupApi.setQueueMembers(q.id, [...members]);
      }
    },
    onSuccess: onClose,
  });
  return (
    <Modal
      open
      onClose={onClose}
      title={`${item ? "Edit" : "New"} ${kind}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => save.mutate()} loading={save.isPending} disabled={!name.trim()}>
            Save
          </Button>
        </>
      }
    >
      <div className="space-y-3 text-sm">
        {save.isError && <Alert tone="error">{errorMessage(save.error)}</Alert>}
        <FormField label="Name" required>
          {({ id }) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} />}
        </FormField>
        {kind === "queue" && (
          <fieldset>
            <legend className="font-medium">Objects this queue can own</legend>
            <div className="mt-1 flex flex-wrap gap-3">
              {objects.map((o) => (
                <label key={o.api} className="flex items-center gap-1.5">
                  <input
                    type="checkbox"
                    checked={objs.has(o.api)}
                    onChange={(e) => {
                      const n = new Set(objs);
                      if (e.target.checked) n.add(o.api);
                      else n.delete(o.api);
                      setObjs(n);
                    }}
                  />
                  {o.label}
                </label>
              ))}
            </div>
          </fieldset>
        )}
        <fieldset>
          <legend className="font-medium">Members</legend>
          <div className="mt-1 grid max-h-64 gap-1 overflow-y-auto sm:grid-cols-2">
            {users.map((u) => (
              <label key={u.id} className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={members.has(u.id)}
                  onChange={(e) => {
                    const n = new Set(members);
                    if (e.target.checked) n.add(u.id);
                    else n.delete(u.id);
                    setMembers(n);
                  }}
                />
                {u.name}
              </label>
            ))}
          </div>
        </fieldset>
      </div>
    </Modal>
  );
}

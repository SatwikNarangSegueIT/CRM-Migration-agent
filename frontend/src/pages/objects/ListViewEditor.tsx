import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { errorMessage } from "../../api/client";
import { recordsApi, type ListViewInput } from "../../api/records";
import type { FilterNode, ListViewDetail, ObjectDescribe } from "../../api/types";
import { cleanFilter, emptyFilter, FilterBuilder } from "../../components/record/FilterBuilder";
import { controlClass } from "../../components/record/FieldInput";
import { ChevronDownIcon, CloseIcon } from "../../components/icons";
import { Alert, Button, FormField, Input } from "../../components/ui";
import { Modal } from "../../components/ui/Modal";
import { useAuth } from "../../auth/context";

/** Create or edit a list view: name, sharing, scope, filters, columns, sort and Kanban grouping. */
export function ListViewEditor({
  meta,
  view,
  onClose,
  onSaved,
}: {
  meta: ObjectDescribe;
  view: ListViewDetail | null;
  onClose: () => void;
  onSaved: (view: ListViewDetail) => void;
}) {
  const { can } = useAuth();
  const queryClient = useQueryClient();
  const canShare = can("manage_public_reports") || can("customize_application");
  const [form, setForm] = useState<ListViewInput>(() => ({
    name: view?.name ?? "",
    visibility: view?.visibility ?? "private",
    scope: view?.scope ?? "all",
    columns: view?.columns.length ? view.columns : meta.list_columns,
    filters: view?.filters && "conditions" in view.filters ? view.filters : emptyFilter(),
    sort: view?.sort ?? [],
    kanban_field: view?.kanban_field ?? null,
    shared_profile_ids: view?.shared_profile_ids ?? [],
    shared_role_ids: view?.shared_role_ids ?? [],
  }));
  const save = useMutation({
    mutationFn: () => {
      const body = { ...form, filters: cleanFilter(form.filters as FilterNode) ?? {} };
      return view ? recordsApi.updateView(meta.api_name, view.id, body) : recordsApi.createView(meta.api_name, body);
    },
    onSuccess: (saved) => {
      void queryClient.invalidateQueries({ queryKey: ["list-views", meta.api_name] });
      void queryClient.invalidateQueries({ queryKey: ["meta", "object", meta.api_name] });
      onSaved(saved);
    },
  });
  const available = Object.values(meta.fields).filter((f) => !form.columns.includes(f.api_name) && f.type !== "encrypted_text");
  const picklists = Object.values(meta.fields).filter((f) => f.type === "picklist");
  const sort = form.sort[0];

  function moveColumn(i: number, delta: number) {
    const cols = [...form.columns];
    const j = i + delta;
    if (j < 0 || j >= cols.length) return;
    [cols[i], cols[j]] = [cols[j]!, cols[i]!];
    setForm({ ...form, columns: cols });
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={view ? `Edit list view: ${view.name}` : "New list view"}
      size="lg"
      busy={save.isPending}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => save.mutate()} loading={save.isPending} disabled={!form.name.trim() || form.columns.length === 0}>
            Save
          </Button>
        </>
      }
    >
      <div className="space-y-5">
        {save.isError && <Alert tone="error">{errorMessage(save.error)}</Alert>}
        <div className="grid gap-4 sm:grid-cols-3">
          <FormField label="List name" required>
            {({ id }) => <Input id={id} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />}
          </FormField>
          <FormField label="Who sees this view">
            {({ id }) => (
              <select id={id} className={controlClass(false)} value={form.visibility} onChange={(e) => setForm({ ...form, visibility: e.target.value as ListViewInput["visibility"] })} disabled={!canShare}>
                <option value="private">Only me</option>
                <option value="public">All users</option>
              </select>
            )}
          </FormField>
          <FormField label="Show">
            {({ id }) => (
              <select id={id} className={controlClass(false)} value={form.scope} onChange={(e) => setForm({ ...form, scope: e.target.value as ListViewInput["scope"] })}>
                <option value="all">All {meta.plural_label.toLowerCase()} I can see</option>
                <option value="mine">My {meta.plural_label.toLowerCase()}</option>
                <option value="team">My team's {meta.plural_label.toLowerCase()}</option>
                {meta.allow_queues && <option value="queue">My queues</option>}
              </select>
            )}
          </FormField>
        </div>
        <section>
          <h3 className="mb-2 text-sm font-semibold text-slate-900">Filters</h3>
          <FilterBuilder meta={meta} value={form.filters as FilterNode} onChange={(filters) => setForm({ ...form, filters })} />
        </section>
        <section>
          <h3 className="mb-2 text-sm font-semibold text-slate-900">Columns</h3>
          <ol className="space-y-1">
            {form.columns.map((c, i) => (
              <li key={c} className="flex items-center justify-between rounded border border-slate-200 bg-white px-3 py-1.5 text-sm">
                <span>{meta.fields[c]?.label ?? c}</span>
                <span className="flex gap-1">
                  <button type="button" aria-label="Move up" className="rounded p-1 hover:bg-slate-100" onClick={() => moveColumn(i, -1)}>
                    <ChevronDownIcon size={14} className="rotate-180" />
                  </button>
                  <button type="button" aria-label="Move down" className="rounded p-1 hover:bg-slate-100" onClick={() => moveColumn(i, 1)}>
                    <ChevronDownIcon size={14} />
                  </button>
                  <button type="button" aria-label={`Remove ${meta.fields[c]?.label ?? c}`} className="rounded p-1 hover:bg-slate-100" onClick={() => setForm({ ...form, columns: form.columns.filter((x) => x !== c) })}>
                    <CloseIcon size={14} />
                  </button>
                </span>
              </li>
            ))}
          </ol>
          <select aria-label="Add column" className={controlClass(false, "mt-2 w-64")} value="" onChange={(e) => e.target.value && setForm({ ...form, columns: [...form.columns, e.target.value] })}>
            <option value="">+ Add column…</option>
            {available.map((f) => (
              <option key={f.api_name} value={f.api_name}>
                {f.label}
              </option>
            ))}
          </select>
        </section>
        <div className="grid gap-4 sm:grid-cols-3">
          <FormField label="Sort by">
            {({ id }) => (
              <select id={id} className={controlClass(false)} value={sort?.field ?? ""} onChange={(e) => setForm({ ...form, sort: e.target.value ? [{ field: e.target.value, direction: sort?.direction ?? "asc" }] : [] })}>
                <option value="">Name</option>
                {Object.values(meta.fields)
                  .filter((f) => f.sortable)
                  .map((f) => (
                    <option key={f.api_name} value={f.api_name}>
                      {f.label}
                    </option>
                  ))}
              </select>
            )}
          </FormField>
          <FormField label="Direction">
            {({ id }) => (
              <select id={id} className={controlClass(false)} value={sort?.direction ?? "asc"} onChange={(e) => setForm({ ...form, sort: [{ field: sort?.field ?? "name", direction: e.target.value as "asc" | "desc" }] })}>
                <option value="asc">Ascending</option>
                <option value="desc">Descending</option>
              </select>
            )}
          </FormField>
          {picklists.length > 0 && (
            <FormField label="Kanban grouping">
              {({ id }) => (
                <select id={id} className={controlClass(false)} value={form.kanban_field ?? ""} onChange={(e) => setForm({ ...form, kanban_field: e.target.value || null })}>
                  <option value="">None</option>
                  {picklists.map((f) => (
                    <option key={f.api_name} value={f.api_name}>
                      {f.label}
                    </option>
                  ))}
                </select>
              )}
            </FormField>
          )}
        </div>
      </div>
    </Modal>
  );
}

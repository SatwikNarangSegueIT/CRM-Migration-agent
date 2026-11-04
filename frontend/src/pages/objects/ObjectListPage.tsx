import {
  keepPreviousData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useCallback, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ApiError, errorMessage } from "../../api/client";
import { downloadPost, recordsApi } from "../../api/records";
import type { FilterNode, ListViewDetail, ObjectDescribe, SortSpec } from "../../api/types";
import { useAuth } from "../../auth/context";
import { ChangeOwnerDialog } from "../../components/record/ChangeOwnerDialog";
import { cleanFilter, emptyFilter, FilterBuilder } from "../../components/record/FilterBuilder";
import { ObjectIcon } from "../../components/record/ObjectIcon";
import { RecordFormModal } from "../../components/record/RecordFormModal";
import {
  ChevronDownIcon,
  ColumnsIcon,
  DownloadIcon,
  FilterIcon,
  GridIcon,
  ListIcon,
  PinIcon,
  PlusIcon,
  SettingsIcon,
  UploadIcon,
} from "../../components/icons";
import {
  Alert,
  Button,
  ButtonGroup,
  ConfirmDialog,
  EmptyState,
  groupButtonClass,
  ListSearch,
  Spinner,
  useToast,
} from "../../components/ui";
import { cx } from "../../components/ui/cx";
import { useObjectMeta, recordPath } from "../../lib/records";
import { metaLine, useRelativeTime } from "../../lib/time";
import { useDismiss } from "../../lib/useDismiss";
import { NotFoundPage } from "../NotFoundPage";
import { KanbanBoard } from "./KanbanBoard";
import { ListTable } from "./ListTable";
import { ListViewEditor } from "./ListViewEditor";

function Menu({
  label,
  icon,
  children,
  align = "right",
}: {
  label: string;
  icon: React.ReactNode;
  children: (close: () => void) => React.ReactNode;
  align?: "left" | "right";
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useDismiss(open, ref, close);
  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={label}
        title={label}
        className="inline-flex h-8 items-center gap-1 rounded-md border border-slate-300 bg-white px-2 text-slate-600 shadow-sm hover:bg-slate-50"
        onClick={() => setOpen((o) => !o)}
      >
        {icon}
        <ChevronDownIcon size={12} />
      </button>
      {open && (
        <div
          role="menu"
          className={cx(
            "absolute z-30 mt-1 w-56 rounded-md border border-slate-200 bg-white py-1 text-sm shadow-lg",
            align === "right" ? "right-0" : "left-0",
          )}
        >
          {children(close)}
        </div>
      )}
    </div>
  );
}

export function MenuItem({
  onClick,
  children,
  danger,
  disabled,
}: {
  onClick: () => void;
  children: React.ReactNode;
  danger?: boolean;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="menuitem"
      disabled={disabled}
      className={cx(
        "block w-full px-3 py-2 text-left hover:bg-slate-50 disabled:text-slate-400",
        danger ? "text-red-700" : "text-slate-800",
      )}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

export function ObjectListPage() {
  const { object = "" } = useParams();
  const meta = useObjectMeta(object);
  if (meta.isPending) return <Spinner label="Loading" />;
  if (meta.isError) {
    if (meta.error instanceof ApiError && meta.error.status === 404) return <NotFoundPage />;
    return <Alert tone="error">{errorMessage(meta.error)}</Alert>;
  }
  return <ListView key={object} meta={meta.data} />;
}

function ListView({ meta }: { meta: ObjectDescribe }) {
  const api = meta.api_name;
  const { can } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const mode = params.get("mode") === "kanban" ? "kanban" : "table";
  const scopeParam = params.get("scope") as "queue" | null;
  const [sort, setSort] = useState<SortSpec | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [filterOpen, setFilterOpen] = useState(false);
  const [adhoc, setAdhoc] = useState<FilterNode>(emptyFilter());
  const [creating, setCreating] = useState(false);
  const [editingView, setEditingView] = useState<ListViewDetail | "new" | null>(null);
  const [ownerOpen, setOwnerOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<"records" | "view" | null>(null);

  const views = useQuery({
    queryKey: ["list-views", api],
    queryFn: ({ signal }) => recordsApi.listViews(api, signal),
  });
  const viewId =
    params.get("view") ??
    views.data?.default_view_id ??
    views.data?.views.find((v) => v.key === `${api}_all`)?.id ??
    views.data?.views[0]?.id ??
    null;
  const view = views.data?.views.find((v) => v.id === viewId) ?? null;
  const columns = view?.columns.length ? view.columns.filter((c) => meta.fields[c]) : meta.list_columns;
  const effectiveSort = sort ?? view?.sort[0] ?? { field: "name", direction: "asc" as const };
  const filters = cleanFilter(adhoc);

  const records = useInfiniteQuery({
    queryKey: ["records", api, viewId, q, sort, filters, scopeParam],
    queryFn: ({ pageParam, signal }) =>
      recordsApi.query(
        api,
        {
          view_id: viewId,
          search: q || null,
          sort: sort ? [sort] : null,
          filters,
          cursor: pageParam,
          limit: 50,
          ...(scopeParam ? { scope: scopeParam } : {}),
        },
        signal,
      ),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    enabled: Boolean(viewId) || views.isError,
    placeholderData: keepPreviousData,
  });
  const rows = useMemo(() => records.data?.pages.flatMap((p) => p.items) ?? [], [records.data]);
  const total = records.data?.pages[0]?.total;
  const capped = records.data?.pages[0]?.total_capped;
  const updated = useRelativeTime(records.dataUpdatedAt || undefined);
  const kanbanField = view?.kanban_field ?? meta.path_field;

  const pin = useMutation({
    mutationFn: () => recordsApi.pinView(api, viewId!),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["list-views", api] });
      toast.show("This list view is now your default.");
    },
  });
  const bulkDelete = useMutation({
    mutationFn: () => recordsApi.bulk(api, { ids: [...selected], operation: "delete" }),
    onSuccess: (r) => {
      setConfirmDelete(null);
      setSelected(new Set());
      void queryClient.invalidateQueries({ queryKey: ["records", api] });
      toast.show(
        `${r.succeeded} deleted${r.failed ? `; ${r.failed} could not be deleted (${r.results.find((x) => !x.ok)?.error ?? ""})` : ""}.`,
        r.failed ? "error" : "success",
      );
    },
    onError: (e) => toast.show(errorMessage(e), "error"),
  });
  const deleteView = useMutation({
    mutationFn: () => recordsApi.deleteView(api, viewId!),
    onSuccess: () => {
      setConfirmDelete(null);
      void queryClient.invalidateQueries({ queryKey: ["list-views", api] });
      setParams({});
    },
    onError: (e) => toast.show(errorMessage(e), "error"),
  });

  function update(changes: Record<string, string | null>) {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(changes)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    setParams(next);
  }

  function onSort(field: string) {
    setSort((cur) => ({
      field,
      direction:
        (cur ?? effectiveSort).field === field && (cur ?? effectiveSort).direction === "asc" ? "desc" : "asc",
    }));
  }

  async function exportCsv() {
    try {
      await downloadPost(
        "/exports",
        { object_api_name: api, view_id: viewId, columns, filters, scope: scopeParam ?? "all" },
        `${api}.csv`,
      );
    } catch (e) {
      toast.show(errorMessage(e), "error");
    }
  }

  const access = meta.access;
  const title = scopeParam === "queue" ? "My Queues" : (view?.name ?? `All ${meta.plural_label}`);
  const sortLabel = meta.fields[effectiveSort.field]?.label ?? "Name";

  return (
    <div className={cx("flex gap-3", filterOpen && "items-start")}>
      <div className="min-w-0 flex-1">
        <div className="rounded-t-lg border border-b-0 border-slate-300 bg-slate-50 px-4 pb-3 pt-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex min-w-0 items-center gap-3">
              <ObjectIcon icon={meta.icon} color={meta.color} size={36} />
              <div className="min-w-0">
                <p className="text-xs text-slate-600">{meta.plural_label}</p>
                <div className="flex items-center gap-1">
                  <ViewPicker
                    views={views.data?.views ?? []}
                    currentId={viewId}
                    title={title}
                    onPick={(id) => update({ view: id, scope: null })}
                  />
                  {viewId && views.data?.default_view_id !== viewId && (
                    <button
                      type="button"
                      aria-label="Pin as default list view"
                      title="Pin as default"
                      className="rounded p-1 text-slate-500 hover:bg-slate-200"
                      onClick={() => pin.mutate()}
                    >
                      <PinIcon size={16} />
                    </button>
                  )}
                </div>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {selected.size > 0 && (access.edit || access.delete) && (
                <ButtonGroup label="Selected records">
                  {access.edit && (
                    <button type="button" className={groupButtonClass} onClick={() => setOwnerOpen(true)}>
                      Change owner
                    </button>
                  )}
                  {access.delete && (
                    <button
                      type="button"
                      className={cx(groupButtonClass, "text-red-700")}
                      onClick={() => setConfirmDelete("records")}
                    >
                      Delete {selected.size}
                    </button>
                  )}
                </ButtonGroup>
              )}
              {((access.create && can("import_data")) || can("export_data")) && (
                <ButtonGroup label="List actions">
                  {access.create && can("import_data") && (
                    <Link to={`/import?object=${api}`} className={groupButtonClass}>
                      <UploadIcon size={16} /> Import
                    </Link>
                  )}
                  {can("export_data") && (
                    <button type="button" className={groupButtonClass} onClick={() => void exportCsv()}>
                      <DownloadIcon size={16} /> Export
                    </button>
                  )}
                </ButtonGroup>
              )}
              {access.create && (
                <Button size="sm" onClick={() => setCreating(true)}>
                  <PlusIcon size={16} /> New
                </Button>
              )}
            </div>
          </div>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-slate-600" aria-live="polite">
              {metaLine([
                total !== undefined && `${total}${capped ? "+" : ""} ${total === 1 ? "item" : "items"}`,
                selected.size > 0 && `${selected.size} selected`,
                mode === "table" && `Sorted by ${sortLabel}`,
                (filters ||
                  (view?.filters && "conditions" in view.filters && view.filters.conditions.length > 0)) &&
                  "Filtered",
                q && `Matching "${q}"`,
                updated && `Updated ${updated}`,
              ])}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <ListSearch key={q} initial={q} onSearch={(value) => update({ q: value || null })} />
              <Menu label="List view controls" icon={<SettingsIcon size={16} />}>
                {(close) => (
                  <>
                    <MenuItem
                      onClick={() => {
                        close();
                        setEditingView("new");
                      }}
                    >
                      New list view
                    </MenuItem>
                    <MenuItem
                      disabled={!view?.can_edit}
                      onClick={() => {
                        close();
                        if (view) setEditingView(view);
                      }}
                    >
                      Edit list filters & columns
                    </MenuItem>
                    <MenuItem
                      disabled={!view?.can_edit || Boolean(view?.key)}
                      danger
                      onClick={() => {
                        close();
                        setConfirmDelete("view");
                      }}
                    >
                      Delete list view
                    </MenuItem>
                  </>
                )}
              </Menu>
              {kanbanField && (
                <div
                  className="inline-flex overflow-hidden rounded-md border border-slate-300 bg-white shadow-sm"
                  role="group"
                  aria-label="Display as"
                >
                  <button
                    type="button"
                    aria-pressed={mode === "table"}
                    title="Table"
                    aria-label="Table"
                    className={cx(
                      "px-2 py-1.5",
                      mode === "table" ? "bg-brand-50 text-brand-700" : "text-slate-600",
                    )}
                    onClick={() => update({ mode: null })}
                  >
                    <ListIcon size={16} />
                  </button>
                  <button
                    type="button"
                    aria-pressed={mode === "kanban"}
                    title="Kanban"
                    aria-label="Kanban"
                    className={cx(
                      "border-l border-slate-300 px-2 py-1.5",
                      mode === "kanban" ? "bg-brand-50 text-brand-700" : "text-slate-600",
                    )}
                    onClick={() => update({ mode: "kanban" })}
                  >
                    <GridIcon size={16} />
                  </button>
                </div>
              )}
              <button
                type="button"
                aria-label="Edit columns"
                title="Edit columns"
                disabled={!view?.can_edit}
                className="inline-flex h-8 items-center rounded-md border border-slate-300 bg-white px-2 text-slate-600 shadow-sm hover:bg-slate-50 disabled:opacity-50"
                onClick={() => view && setEditingView(view)}
              >
                <ColumnsIcon size={16} />
              </button>
              <button
                type="button"
                aria-pressed={filterOpen}
                aria-label="Show filters"
                title="Filters"
                className={cx(
                  "inline-flex h-8 items-center rounded-md border px-2 shadow-sm",
                  filterOpen || filters
                    ? "border-brand-500 bg-brand-50 text-brand-700"
                    : "border-slate-300 bg-white text-slate-600 hover:bg-slate-50",
                )}
                onClick={() => setFilterOpen((o) => !o)}
              >
                <FilterIcon size={16} />
              </button>
            </div>
          </div>
        </div>
        {records.isError && <Alert tone="error">{errorMessage(records.error)}</Alert>}
        {mode === "kanban" && kanbanField ? (
          <KanbanBoard meta={meta} field={kanbanField} viewId={viewId} q={q} />
        ) : (
          <ListTable
            meta={meta}
            columns={columns}
            rows={rows}
            loading={records.isPending || views.isPending}
            sort={effectiveSort}
            onSort={onSort}
            selected={selected}
            onSelect={setSelected}
            empty={
              <EmptyState
                title={q || filters ? "No matching records" : `No ${meta.plural_label.toLowerCase()} yet`}
                description={
                  q || filters
                    ? "Try a different search or remove filters."
                    : `${meta.plural_label} you can see appear here.`
                }
                icon={<ObjectIcon icon={meta.icon} color={meta.color} size={44} />}
                action={
                  access.create && !q && !filters
                    ? { label: `Add a ${meta.label}`, onClick: () => setCreating(true) }
                    : undefined
                }
              />
            }
            footer={
              records.hasNextPage && (
                <div className="border-t border-slate-200 p-2 text-center">
                  <Button
                    variant="secondary"
                    size="sm"
                    loading={records.isFetchingNextPage}
                    onClick={() => void records.fetchNextPage()}
                  >
                    Load more
                  </Button>
                </div>
              )
            }
          />
        )}
      </div>

      {filterOpen && (
        <aside
          aria-label="Filters"
          className="w-full max-w-sm flex-none rounded-lg border border-slate-300 bg-white p-4 shadow-sm"
        >
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold text-slate-900">Filters</h2>
            <button
              type="button"
              className="text-sm text-brand-700 hover:underline"
              onClick={() => setAdhoc(emptyFilter())}
            >
              Remove all
            </button>
          </div>
          <p className="mb-3 text-xs text-slate-500">
            Applied on top of the list view's own filters. Save them into the view with "Edit list filters".
          </p>
          <FilterBuilder meta={meta} value={adhoc} onChange={setAdhoc} />
        </aside>
      )}

      {creating && (
        <RecordFormModal
          meta={meta}
          record={null}
          open
          onClose={() => setCreating(false)}
          onSaved={(r) => {
            setCreating(false);
            toast.show(`${meta.label} "${r.name}" was created.`);
            navigate(recordPath(api, r.id));
          }}
        />
      )}
      {editingView && (
        <ListViewEditor
          meta={meta}
          view={editingView === "new" ? null : editingView}
          onClose={() => setEditingView(null)}
          onSaved={(v) => {
            setEditingView(null);
            update({ view: v.id });
            toast.show(`List view "${v.name}" saved.`);
          }}
        />
      )}
      {ownerOpen && (
        <ChangeOwnerDialog
          object={api}
          ids={[...selected]}
          allowQueues={meta.allow_queues}
          onClose={() => setOwnerOpen(false)}
          onDone={(message) => {
            setOwnerOpen(false);
            setSelected(new Set());
            toast.show(message);
            void queryClient.invalidateQueries({ queryKey: ["records", api] });
          }}
        />
      )}
      <ConfirmDialog
        open={confirmDelete !== null}
        title={confirmDelete === "view" ? "Delete list view?" : `Delete ${selected.size} record(s)?`}
        tone="danger"
        confirmLabel="Delete"
        loading={bulkDelete.isPending || deleteView.isPending}
        onCancel={() => setConfirmDelete(null)}
        onConfirm={() => (confirmDelete === "view" ? deleteView.mutate() : bulkDelete.mutate())}
      >
        {confirmDelete === "view"
          ? "The view is removed for everyone who uses it."
          : "Deleted records go to the recycle bin for 30 days."}
      </ConfirmDialog>
    </div>
  );
}

function ViewPicker({
  views,
  currentId,
  title,
  onPick,
}: {
  views: ListViewDetail[];
  currentId: string | null;
  title: string;
  onPick: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useDismiss(open, ref, close);
  const shipped = views.filter((v) => v.key);
  const mine = views.filter((v) => !v.key && v.is_mine);
  const shared = views.filter((v) => !v.key && !v.is_mine);
  const group = (label: string, list: ListViewDetail[]) =>
    list.length > 0 && (
      <div>
        <p className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
          {label}
        </p>
        {list.map((v) => (
          <button
            key={v.id}
            type="button"
            role="menuitemradio"
            aria-checked={v.id === currentId}
            className={cx(
              "block w-full px-3 py-1.5 text-left hover:bg-slate-50",
              v.id === currentId && "font-semibold text-brand-700",
            )}
            onClick={() => {
              onPick(v.id);
              close();
            }}
          >
            {v.name}
          </button>
        ))}
      </div>
    );
  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-1 text-lg font-bold text-slate-900 hover:text-brand-700"
        onClick={() => setOpen((o) => !o)}
      >
        <h1 className="truncate">{title}</h1>
        <ChevronDownIcon size={18} />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute left-0 z-30 mt-1 max-h-96 w-72 overflow-y-auto rounded-md border border-slate-200 bg-white py-1 text-sm shadow-lg"
        >
          {group("List views", shipped)}
          {group("My views", mine)}
          {group("Shared views", shared)}
        </div>
      )}
    </div>
  );
}

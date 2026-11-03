import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AUDIT_ACTIONS, auditApi, type AuditLog } from "../../api/audit";
import { errorMessage } from "../../api/client";
import { ClipboardIcon, RefreshIcon } from "../../components/icons";
import {
  Alert,
  Badge,
  Button,
  ButtonGroup,
  DataTable,
  EmptyState,
  groupButtonClass,
  Input,
  ListViewHeader,
  Pagination,
  Select,
  type Column,
} from "../../components/ui";
import { metaLine, useRelativeTime } from "../../lib/time";
import { formatDateTime } from "../../lib/format";

const PAGE_SIZE = 50;

function actionTone(action: string) {
  if (/FAILED|LOCKED|DELETE|RESET$|REVOKED/.test(action)) return "red" as const;
  if (/LOGIN|LOGOUT/.test(action)) return "blue" as const;
  if (action === "CREATE") return "green" as const;
  return "gray" as const;
}

/** yyyy-mm-dd (local) -> ISO instant at local midnight; `addDays` moves the boundary. */
function dayStartIso(day: string, addDays = 0): string | undefined {
  if (!day) return undefined;
  const [y, m, d] = day.split("-").map(Number);
  if (!y || !m || !d) return undefined;
  return new Date(y, m - 1, d + addDays).toISOString();
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function Changes({ changes }: { changes: Record<string, unknown> }) {
  const entries = Object.entries(changes);
  return (
    <table className="text-xs">
      <thead>
        <tr className="text-left text-slate-500">
          <th className="pr-6 font-medium">Field</th>
          <th className="pr-6 font-medium">From</th>
          <th className="font-medium">To</th>
        </tr>
      </thead>
      <tbody>
        {entries.map(([field, change]) => {
          const isDiff = typeof change === "object" && change !== null && "from" in change && "to" in change;
          const c = change as { from?: unknown; to?: unknown };
          return (
            <tr key={field}>
              <td className="pr-6 font-mono text-slate-700">{field}</td>
              <td className="pr-6 text-slate-600">{isDiff ? formatValue(c.from) : "—"}</td>
              <td className="text-slate-900">{isDiff ? formatValue(c.to) : formatValue(change)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export function AuditLogPage() {
  const [params, setParams] = useSearchParams();
  const page = Math.max(1, Number(params.get("page")) || 1);
  const action = params.get("action") ?? "";
  const entityType = params.get("entity_type") ?? "";
  const from = params.get("from") ?? "";
  const to = params.get("to") ?? "";
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const logs = useQuery({
    queryKey: ["audit", { page, action, entityType, from, to }],
    queryFn: ({ signal }) =>
      auditApi.list(
        {
          page,
          page_size: PAGE_SIZE,
          action: action || undefined,
          entity_type: entityType || undefined,
          date_from: dayStartIso(from),
          date_to: dayStartIso(to, 1),
        },
        signal,
      ),
    placeholderData: keepPreviousData,
  });
  const updated = useRelativeTime(logs.dataUpdatedAt || undefined);
  const filtered = Boolean(action || entityType || from || to);

  function update(changes: Record<string, string>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    if (!("page" in changes)) next.delete("page");
    setParams(next);
  }

  function toggle(id: string) {
    setExpanded((set) => {
      const next = new Set(set);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const columns: Column<AuditLog>[] = [
    {
      key: "when",
      header: "When",
      render: (r) => <span className="whitespace-nowrap">{formatDateTime(r.created_at)}</span>,
    },
    { key: "action", header: "Action", render: (r) => <Badge tone={actionTone(r.action)}>{r.action}</Badge> },
    {
      key: "actor",
      header: "User",
      render: (r) =>
        r.actor ? (
          <span>
            <span className="block">{r.actor.name}</span>
            <span className="block text-xs text-slate-500">{r.actor.email}</span>
          </span>
        ) : (
          <span className="text-slate-500">System / anonymous</span>
        ),
    },
    {
      key: "entity",
      header: "Record",
      render: (r) => <span className="font-mono text-xs">{r.entity_type}</span>,
    },
    { key: "summary", header: "Summary", render: (r) => r.summary },
    {
      key: "details",
      header: <span className="sr-only">Details</span>,
      noMenu: true,
      render: (r) => (
        <Button size="sm" variant="ghost" aria-expanded={expanded.has(r.id)} onClick={() => toggle(r.id)}>
          {expanded.has(r.id) ? "Hide" : "Details"}
        </Button>
      ),
    },
  ];

  return (
    <div>
      <ListViewHeader
        objectLabel="Audit Log"
        title={filtered ? "Filtered Entries" : "All Entries"}
        icon={<ClipboardIcon size={20} />}
        iconClassName="bg-violet-600"
        meta={metaLine([
          logs.data && `${logs.data.total} ${logs.data.total === 1 ? "item" : "items"}`,
          "Sorted by Date (newest first)",
          action && `Action: ${action}`,
          updated && `Updated ${updated}`,
        ])}
        actions={
          <ButtonGroup label="List actions">
            <button
              type="button"
              className={groupButtonClass}
              onClick={() => void logs.refetch()}
              disabled={logs.isFetching}
            >
              <RefreshIcon size={16} />
              Refresh
            </button>
            <button
              type="button"
              className={groupButtonClass}
              onClick={() => setParams(new URLSearchParams())}
              disabled={!filtered}
            >
              Clear filters
            </button>
          </ButtonGroup>
        }
        toolbar={
          <>
            <label htmlFor="audit-action" className="sr-only">
              Action
            </label>
            <div className="w-44">
              <Select
                id="audit-action"
                className="h-8 py-0"
                value={action}
                onChange={(e) => update({ action: e.target.value })}
              >
                <option value="">All actions</option>
                {AUDIT_ACTIONS.map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </Select>
            </div>
            <label htmlFor="audit-entity" className="sr-only">
              Record type
            </label>
            <div className="w-44">
              <Select
                id="audit-entity"
                className="h-8 py-0"
                value={entityType}
                onChange={(e) => update({ entity_type: e.target.value })}
              >
                <option value="">All record types</option>
                <option value="user">User</option>
              </Select>
            </div>
            <label htmlFor="audit-from" className="text-xs text-slate-600">
              From
            </label>
            <div className="w-40">
              <Input
                id="audit-from"
                type="date"
                className="h-8 py-0"
                value={from}
                onChange={(e) => update({ from: e.target.value })}
              />
            </div>
            <label htmlFor="audit-to" className="text-xs text-slate-600">
              To
            </label>
            <div className="w-40">
              <Input
                id="audit-to"
                type="date"
                className="h-8 py-0"
                value={to}
                onChange={(e) => update({ to: e.target.value })}
              />
            </div>
          </>
        }
      />
      {logs.isError && <Alert tone="error">{errorMessage(logs.error)}</Alert>}
      <DataTable
        caption="Audit log entries"
        columns={columns}
        rows={logs.data?.items}
        rowKey={(r) => r.id}
        loading={logs.isPending}
        attached
        emptyMessage={
          <EmptyState
            title={filtered ? "No entries match these filters" : "No audit entries yet"}
            description={
              filtered ? "Try a wider date range or another action." : "Sign-ins and changes appear here."
            }
            action={
              filtered
                ? { label: "Clear filters", onClick: () => setParams(new URLSearchParams()) }
                : undefined
            }
          />
        }
        renderExpanded={(r) =>
          expanded.has(r.id) ? (
            <div className="space-y-2 text-xs text-slate-600">
              {r.changes && Object.keys(r.changes).length > 0 ? (
                <Changes changes={r.changes} />
              ) : (
                <p>No field changes recorded.</p>
              )}
              <p>
                Record ID: <span className="font-mono">{r.entity_id ?? "—"}</span> · IP: {r.ip_address ?? "—"}{" "}
                · Request: <span className="font-mono">{r.request_id ?? "—"}</span>
              </p>
              {r.user_agent && <p className="break-all">Browser: {r.user_agent}</p>}
            </div>
          ) : null
        }
      />
      {logs.data && logs.data.total > 0 && (
        <Pagination
          page={logs.data.page}
          pageSize={logs.data.page_size}
          total={logs.data.total}
          onPageChange={(p) => update({ page: String(p) })}
        />
      )}
    </div>
  );
}

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { errorMessage } from "../../api/client";
import type { Role } from "../../api/types";
import { usersApi, type User } from "../../api/users";
import { PlusIcon, RefreshIcon, UsersIcon } from "../../components/icons";
import {
  Alert,
  ButtonGroup,
  DataTable,
  EmptyState,
  groupButtonClass,
  ListSearch,
  ListViewHeader,
  Pagination,
  Select,
  type Column,
} from "../../components/ui";
import { formatDateTime } from "../../lib/format";
import { metaLine, useRelativeTime } from "../../lib/time";
import { UserStatusBadges } from "./UserStatusBadges";
import { useStaffRoles } from "./useStaffRoles";

const PAGE_SIZE = 25;

const COLUMNS: Column<User>[] = [
  {
    key: "name",
    header: "Name",
    render: (u) => (
      <Link to={`/admin/users/${u.id}`} className="font-medium text-brand-700 hover:underline">
        {u.name}
      </Link>
    ),
  },
  { key: "email", header: "E-mail", render: (u) => <span className="break-all">{u.email}</span> },
  { key: "role", header: "Role", render: (u) => u.role_label },
  { key: "status", header: "Status", render: (u) => <UserStatusBadges user={u} /> },
  {
    key: "last_login",
    header: "Last sign-in",
    render: (u) => <span className="whitespace-nowrap">{formatDateTime(u.last_login_at)}</span>,
  },
];

const compactSelect = "h-8 py-0 text-sm";

export function UsersListPage() {
  const [params, setParams] = useSearchParams();
  const page = Math.max(1, Number(params.get("page")) || 1);
  const q = params.get("q") ?? "";
  const role = (params.get("role") ?? "") as Role | "";
  const status = params.get("status") ?? "";
  const roles = useStaffRoles();

  const users = useQuery({
    queryKey: ["users", { page, q, role, status }],
    queryFn: ({ signal }) =>
      usersApi.list(
        {
          page,
          page_size: PAGE_SIZE,
          q: q || undefined,
          role: role || undefined,
          is_active: status === "" ? undefined : status === "active",
        },
        signal,
      ),
    placeholderData: keepPreviousData,
  });
  const updated = useRelativeTime(users.dataUpdatedAt || undefined);

  function update(changes: Record<string, string>) {
    const nextParams = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) nextParams.set(key, value);
      else nextParams.delete(key);
    }
    if (!("page" in changes)) nextParams.delete("page");
    setParams(nextParams);
  }

  const filtered = Boolean(q || role || status);
  const total = users.data?.total;
  const title = status === "active" ? "Active Users" : status === "inactive" ? "Inactive Users" : "All Users";
  const roleLabel = roles.data?.find((r) => r.value === role)?.label;

  return (
    <div>
      <ListViewHeader
        objectLabel="Users"
        title={title}
        icon={<UsersIcon size={20} />}
        meta={metaLine([
          total !== undefined && `${total} ${total === 1 ? "item" : "items"}`,
          "Sorted by Name",
          roleLabel && `Filtered by role: ${roleLabel}`,
          q && `Matching "${q}"`,
          updated && `Updated ${updated}`,
        ])}
        actions={
          <ButtonGroup label="List actions">
            <Link to="/admin/users/new" className={groupButtonClass}>
              <PlusIcon size={16} />
              New
            </Link>
            <button
              type="button"
              className={groupButtonClass}
              onClick={() => void users.refetch()}
              disabled={users.isFetching}
            >
              <RefreshIcon size={16} />
              Refresh
            </button>
          </ButtonGroup>
        }
        toolbar={
          <>
            <ListSearch key={q} initial={q} onSearch={(value) => update({ q: value })} label="Search users" />
            <label htmlFor="role-filter" className="sr-only">
              Role
            </label>
            <div className="w-44">
              <Select
                id="role-filter"
                className={compactSelect}
                value={role}
                onChange={(e) => update({ role: e.target.value })}
              >
                <option value="">All roles</option>
                {roles.data?.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </Select>
            </div>
            <label htmlFor="status-filter" className="sr-only">
              Status
            </label>
            <div className="w-44">
              <Select
                id="status-filter"
                className={compactSelect}
                value={status}
                onChange={(e) => update({ status: e.target.value })}
              >
                <option value="">All statuses</option>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </Select>
            </div>
          </>
        }
      />
      {users.isError && <Alert tone="error">{errorMessage(users.error)}</Alert>}
      <DataTable
        attached
        caption="Users"
        columns={COLUMNS}
        rows={users.data?.items}
        rowKey={(u) => u.id}
        loading={users.isPending}
        emptyMessage={
          filtered ? (
            <EmptyState
              title="No users match this view"
              description="Try a different search or clear the filters."
              action={{ label: "Clear filters", onClick: () => setParams(new URLSearchParams()) }}
            />
          ) : (
            <EmptyState
              title="No users yet"
              description="Invite your team to start working in MigrateCRM."
              action={{ label: "New user", to: "/admin/users/new" }}
            />
          )
        }
      />
      {users.data && users.data.total > 0 && (
        <Pagination
          page={users.data.page}
          pageSize={users.data.page_size}
          total={users.data.total}
          onPageChange={(p) => update({ page: String(p) })}
        />
      )}
    </div>
  );
}

import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { User } from "../../api/users";
import { errorResponse, jsonResponse, makeMe, mockApi, renderRoute } from "../../test/utils";

const ROLES = [
  { value: "ADMIN", label: "Administrator", is_staff: true, permissions: {} },
  { value: "CASE_OFFICER", label: "Case Officer", is_staff: true, permissions: {} },
  { value: "CLIENT", label: "Client", is_staff: false, permissions: {} },
];

function user(overrides: Partial<User> = {}): User {
  return {
    id: "u-2",
    email: "casey@example.com",
    name: "Casey Officer",
    role: "CASE_OFFICER",
    role_label: "Case Officer",
    is_active: true,
    title: null,
    phone: null,
    mara_number: null,
    mfa_enabled: false,
    last_login_at: null,
    locked_until: null,
    created_at: "2026-11-01T00:00:00Z",
    updated_at: "2026-11-02T03:04:05.123456Z",
    has_password: false,
    ...overrides,
  };
}

describe("users list", () => {
  it("renders users with status badges and a list-view summary", async () => {
    mockApi({
      "GET /auth/me": makeMe(),
      "GET /meta/roles": ROLES,
      "GET /admin/users": {
        items: [
          user(),
          user({ id: "u-3", name: "Lou Locked", has_password: true, locked_until: "2999-01-01T00:00:00Z" }),
        ],
        total: 2,
        page: 1,
        page_size: 25,
      },
    });
    renderRoute("/admin/users");
    expect(await screen.findByRole("link", { name: "Casey Officer" })).toHaveAttribute(
      "href",
      "/admin/users/u-2",
    );
    expect(screen.getByRole("heading", { name: "All Users" })).toBeInTheDocument();
    expect(screen.getByText(/2 items • Sorted by Name/)).toBeInTheDocument();
    expect(screen.getByText("Invited")).toBeInTheDocument();
    expect(screen.getByText("Locked")).toBeInTheDocument();
  });

  it("passes search and filters to the API via the URL", async () => {
    const fetchSpy = mockApi({
      "GET /auth/me": makeMe(),
      "GET /meta/roles": ROLES,
      "GET /admin/users": { items: [], total: 0, page: 1, page_size: 25 },
    });
    const { router } = renderRoute("/admin/users");
    expect(await screen.findByText("No users yet")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "inactive" } });
    await waitFor(() => expect(router.state.location.search).toBe("?status=inactive"));
    fireEvent.change(screen.getByLabelText("Search users"), { target: { value: "casey" } });
    fireEvent.submit(screen.getByLabelText("Search users").closest("form")!);
    await waitFor(() => {
      const urls = fetchSpy.mock.calls.map((c) => String(c[0]));
      expect(urls).toContain("/api/v1/admin/users?page=1&page_size=25&q=casey&is_active=false");
    });
    expect(await screen.findByText("No users match this view")).toBeInTheDocument();
    // CLIENT is not offered as a staff role.
    const roleSelect = screen.getByLabelText("Role");
    expect(within(roleSelect).queryByText("Client")).not.toBeInTheDocument();
  });
});

describe("user detail", () => {
  it("sends updated_at with changes and explains a 409 conflict", async () => {
    let body: Record<string, unknown> | null = null;
    mockApi({
      "GET /auth/me": makeMe(),
      "GET /meta/roles": ROLES,
      "GET /admin/users/u-2": user(),
      "PATCH /admin/users/u-2": (init: RequestInit) => {
        body = JSON.parse(String(init.body)) as Record<string, unknown>;
        return errorResponse(409, "conflict", "This user was changed by someone else.", {
          updated_at: "Stale",
        });
      },
    });
    renderRoute("/admin/users/u-2");
    const name = await screen.findByLabelText(/Full name/);
    fireEvent.change(name, { target: { value: "Casey O'Brien" } });
    fireEvent.change(screen.getByLabelText(/Job title/), { target: { value: "Senior Case Officer" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByText("This user was changed by someone else")).toBeInTheDocument();
    expect(body).toEqual({
      updated_at: "2026-11-02T03:04:05.123456Z",
      name: "Casey O'Brien",
      title: "Senior Case Officer",
    });
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
  });

  it("confirms actions in a dialog and prevents self-deactivation", async () => {
    let resent = false;
    mockApi({
      "GET /auth/me": makeMe({ id: "u-2" }),
      "GET /meta/roles": ROLES,
      "GET /admin/users/u-2": user(),
      "POST /admin/users/u-2/resend-invitation": () => {
        resent = true;
        return jsonResponse({ message: "Invitation sent to casey@example.com." });
      },
    });
    renderRoute("/admin/users/u-2");
    expect(await screen.findByRole("button", { name: "Deactivate" })).toBeDisabled();
    expect(screen.getByLabelText(/Role/)).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Resend invitation" }));
    const dialog = await screen.findByRole("dialog", { name: "Resend invitation?" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Resend invitation" }));
    expect(await screen.findByText("Invitation sent to casey@example.com.")).toBeInTheDocument();
    expect(resent).toBe(true);
  });
});

import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { MeResponse } from "../api/auth";
import { errorResponse, jsonResponse, makeMe, mockApi, renderRoute, shellHandlers } from "../test/utils";

const HEALTH = shellHandlers();
const GREETING = /^Good (morning|afternoon|evening), Alex$/;

/** /auth/me returns 401 until login succeeds, then `afterLogin`. */
function loginScenario(state: string, afterLogin: MeResponse | null) {
  let signedIn = false;
  return mockApi({
    ...HEALTH,
    "GET /auth/me": () =>
      signedIn && afterLogin
        ? jsonResponse(afterLogin)
        : errorResponse(401, "unauthenticated", "Please sign in."),
    "POST /auth/login": () => {
      signedIn = true;
      return jsonResponse({ state });
    },
  });
}

async function submitLogin() {
  fireEvent.change(await screen.findByLabelText(/E-mail/), { target: { value: "admin@demo.example.com" } });
  fireEvent.change(screen.getByLabelText(/Password/), { target: { value: "Demo-Password-2026!" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
}

describe("route guards", () => {
  it("sends signed-out users to the login page, keeping the destination", async () => {
    mockApi({ "GET /auth/me": () => errorResponse(401, "unauthenticated") });
    const { router } = renderRoute("/admin/users?page=2");
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/login");
    expect(router.state.location.search).toBe("?next=%2Fadmin%2Fusers%3Fpage%3D2");
  });

  it("sends clients to the portal", async () => {
    mockApi({
      "GET /auth/me": makeMe({ profile: "Customer Portal User", name: "Priya Client" }),
      "GET /portal/me": { contact: null, account: null, objects: [], counts: {}, branding: {} },
    });
    const { router } = renderRoute("/");
    expect(await screen.findByRole("heading", { name: "Hello, Priya" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/portal");
  });

  it("sends staff away from the portal", async () => {
    mockApi({ ...HEALTH, "GET /auth/me": makeMe() });
    const { router } = renderRoute("/portal");
    await screen.findByRole("heading", { name: GREETING });
    expect(router.state.location.pathname).toBe("/");
  });

  it("shows access denied without the permission", async () => {
    mockApi({
      ...HEALTH,
      "GET /auth/me": makeMe({
        profile: "Read Only (Auditor)",
        permissions: ["export_data", "view_audit_log", "view_setup"],
      }),
    });
    const { router } = renderRoute("/admin/users");
    expect(await screen.findByRole("heading", { name: "Access denied" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/forbidden");
  });

  it("sends a session waiting for MFA to the verification step", async () => {
    mockApi({ "GET /auth/me": makeMe({ mfa_verified: false, mfa_enabled: true }) });
    const { router } = renderRoute("/admin/audit");
    expect(await screen.findByRole("heading", { name: "Two-step verification" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/mfa");
  });

  it("shows only permitted Setup pages in the navigation", async () => {
    mockApi({
      ...HEALTH,
      "GET /auth/me": makeMe({
        profile: "Read Only (Auditor)",
        permissions: ["export_data", "view_audit_log", "view_setup"],
      }),
      "GET /admin/audit-logs": { items: [], total: 0, page: 1, page_size: 50 },
    });
    renderRoute("/admin/audit");
    const setup = await screen.findByRole("navigation", { name: "Setup" });
    expect(setup).toHaveTextContent("Audit Log");
    expect(setup).toHaveTextContent("Profiles");
    expect(setup).not.toHaveTextContent("Portal Users");
    expect(screen.queryByRole("link", { name: "Users" })).not.toBeInTheDocument();
  });

  it("hides Setup when no setup permission is held and lists the user's apps", async () => {
    mockApi({
      ...HEALTH,
      "GET /auth/me": makeMe({ profile: "Sales Representative", objects: { account: { read: true } } }),
    });
    renderRoute("/");
    const rail = await screen.findByRole("navigation", { name: "Apps" });
    await waitFor(() => expect(rail).toHaveTextContent("Sales"));
    expect(rail).toHaveTextContent("Home");
    expect(rail).toHaveTextContent("Accounts");
    expect(rail).not.toHaveTextContent("Contacts");
    expect(rail).not.toHaveTextContent("Setup");
    expect(screen.queryByRole("button", { name: "Setup" })).not.toBeInTheDocument();
  });

  it("returns to login when a request reports the session has ended", async () => {
    let expired = false;
    mockApi({
      ...HEALTH,
      "GET /auth/me": () => (expired ? errorResponse(401, "unauthenticated") : jsonResponse(makeMe())),
      "GET /admin/users": () => {
        expired = true;
        return errorResponse(401, "unauthenticated", "Please sign in.");
      },
      "GET /setup/profiles": [],
      "GET /setup/roles": [],
    });
    const { router } = renderRoute("/admin/users");
    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
  });
});

describe("login flow", () => {
  it("goes to the requested page after signing in", async () => {
    loginScenario("authenticated", makeMe());
    const { router } = renderRoute("/login?next=%2Faccount");
    await submitLogin();
    expect(await screen.findByRole("heading", { name: "Account settings" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/account");
  });

  it("asks for the MFA code when required", async () => {
    loginScenario("mfa_required", makeMe({ mfa_verified: false, mfa_enabled: true }));
    const { router } = renderRoute("/login");
    await submitLogin();
    expect(await screen.findByLabelText(/Authentication code/)).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/mfa");
  });

  it("starts MFA set-up when the account has none", async () => {
    loginScenario("mfa_setup_required", makeMe({ mfa_verified: false, mfa_setup_required: true }));
    const { router } = renderRoute("/login");
    await submitLogin();
    expect(await screen.findByRole("heading", { name: "Set up two-step verification" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/mfa/setup");
  });

  it("shows the server error for bad credentials", async () => {
    mockApi({
      "GET /auth/me": () => errorResponse(401, "unauthenticated"),
      "POST /auth/login": () => errorResponse(401, "invalid_credentials", "Invalid e-mail or password."),
    });
    renderRoute("/login");
    await submitLogin();
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid e-mail or password.");
  });

  it("completes MFA verification and continues", async () => {
    let verified = false;
    mockApi({
      ...HEALTH,
      "GET /auth/me": () =>
        jsonResponse(verified ? makeMe() : makeMe({ mfa_verified: false, mfa_enabled: true })),
      "POST /auth/mfa/verify": (init: RequestInit) => {
        expect(JSON.parse(String(init.body))).toEqual({ code: "123456" });
        verified = true;
        return jsonResponse(makeMe());
      },
    });
    const { router } = renderRoute("/mfa?next=%2F");
    fireEvent.change(await screen.findByLabelText(/Authentication code/), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Verify" }));
    expect(await screen.findByRole("heading", { name: GREETING })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/");
  });

  it("shows an invalid MFA code as a field error", async () => {
    mockApi({
      "GET /auth/me": makeMe({ mfa_verified: false, mfa_enabled: true }),
      "POST /auth/mfa/verify": () =>
        errorResponse(422, "invalid_code", "The code is not valid.", { code: "Invalid code" }),
    });
    renderRoute("/mfa");
    fireEvent.change(await screen.findByLabelText(/Authentication code/), { target: { value: "000000" } });
    fireEvent.click(screen.getByRole("button", { name: "Verify" }));
    expect(await screen.findByText(/That code is not valid/)).toBeInTheDocument();
  });
});

describe("account page", () => {
  it("shows an incorrect current password as a field error without signing out", async () => {
    mockApi({
      "GET /auth/me": makeMe(),
      "POST /auth/password/change": () =>
        errorResponse(422, "incorrect_password", "Current password is incorrect.", {
          current_password: "Incorrect password",
        }),
    });
    const { router } = renderRoute("/account");
    fireEvent.change(await screen.findByLabelText(/Current password/), {
      target: { value: "wrong-password!" },
    });
    fireEvent.change(screen.getByLabelText(/^New password/), { target: { value: "a-brand-new-passphrase" } });
    fireEvent.change(screen.getByLabelText(/Confirm password/), {
      target: { value: "a-brand-new-passphrase" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Update password" }));
    expect(await screen.findByText("Incorrect password")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/account");
  });
});

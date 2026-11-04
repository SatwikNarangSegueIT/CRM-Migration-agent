import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { errorResponse, jsonResponse, makeMe, mockApi, renderRoute, shellHandlers } from "../../test/utils";

const DOMAINS = [
  { key: "legal", label: "Law firm", profession: "Lawyers", description: "Matters.", includes: [] },
  { key: "migration", label: "Migration agency", profession: "Agents", description: "Visas.", includes: [] },
];

describe("sign-up", () => {
  it("chooses a domain, then sends the details for verification", async () => {
    let sent: Record<string, unknown> | null = null;
    mockApi({
      "GET /auth/me": () => errorResponse(401, "unauthenticated"),
      "GET /signup/domains": DOMAINS,
      "POST /signup": (init: RequestInit) => {
        sent = JSON.parse(String(init.body)) as Record<string, unknown>;
        return jsonResponse({ message: "ok" }, 202);
      },
    });
    renderRoute("/signup");
    const cont = await screen.findByRole("button", { name: "Continue" });
    expect(cont).toBeDisabled();
    fireEvent.click(screen.getByRole("radio", { name: /Law firm/ }));
    fireEvent.click(cont);

    fireEvent.change(await screen.findByLabelText(/Firm name/), { target: { value: "Harbour Legal" } });
    fireEvent.change(screen.getByLabelText(/Your name/), { target: { value: "Hana Harbour" } });
    fireEvent.change(screen.getByLabelText(/Work e-mail/), { target: { value: "hana@example.com" } });
    fireEvent.change(screen.getByLabelText(/^Password/), { target: { value: "Fresh-Firm-Password-77" } });
    fireEvent.change(screen.getByLabelText(/Confirm/), { target: { value: "Fresh-Firm-Password-77" } });
    const create = screen.getByRole("button", { name: "Create workspace" });
    expect(create).toBeDisabled();
    fireEvent.click(screen.getByLabelText(/I agree to the terms/));
    fireEvent.click(create);

    expect(await screen.findByRole("heading", { name: "Check your inbox" })).toBeInTheDocument();
    expect(sent).toMatchObject({
      domain: "legal",
      firm_name: "Harbour Legal",
      accept_terms: true,
      abn: null,
    });
  });
});

describe("sign-up without e-mail set up", () => {
  it("signs straight in when the server creates the workspace at once", async () => {
    let signedIn = false;
    mockApi({
      ...shellHandlers(),
      "GET /auth/me": () => (signedIn ? jsonResponse(makeMe()) : errorResponse(401, "unauthenticated")),
      "GET /signup/domains": DOMAINS,
      "POST /signup": () => {
        signedIn = true;
        return jsonResponse({ state: "authenticated", workspace: { slug: "harbour", name: "Harbour" } }, 201);
      },
    });
    renderRoute("/signup");
    fireEvent.click(await screen.findByRole("radio", { name: /Law firm/ }));
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    fireEvent.change(await screen.findByLabelText(/Firm name/), { target: { value: "Harbour" } });
    fireEvent.change(screen.getByLabelText(/Your name/), { target: { value: "Hana Harbour" } });
    fireEvent.change(screen.getByLabelText(/Work e-mail/), { target: { value: "hana@example.com" } });
    fireEvent.change(screen.getByLabelText(/^Password/), { target: { value: "Fresh-Firm-Password-77" } });
    fireEvent.change(screen.getByLabelText(/Confirm/), { target: { value: "Fresh-Firm-Password-77" } });
    fireEvent.click(screen.getByLabelText(/I agree to the terms/));
    fireEvent.click(screen.getByRole("button", { name: "Create workspace" }));

    expect(
      await screen.findByRole("heading", { name: /^Good (morning|afternoon|evening), Alex$/ }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Check your inbox" })).not.toBeInTheDocument();
  });
});

describe("workspace picker", () => {
  it("asks which firm when the e-mail belongs to several, then signs in to the chosen one", async () => {
    const bodies: Record<string, unknown>[] = [];
    let signedIn = false;
    mockApi({
      ...shellHandlers(),
      "GET /auth/me": () => (signedIn ? jsonResponse(makeMe()) : errorResponse(401, "unauthenticated")),
      "POST /auth/login": (init: RequestInit) => {
        const body = JSON.parse(String(init.body)) as Record<string, unknown>;
        bodies.push(body);
        if (!body.workspace) {
          return jsonResponse({
            state: "choose_workspace",
            workspaces: [
              { slug: "main", name: "First Firm", domain: "migration" },
              { slug: "second", name: "Second Firm", domain: "legal" },
            ],
          });
        }
        signedIn = true;
        return jsonResponse({ state: "authenticated" });
      },
    });
    const { router } = renderRoute("/login");
    fireEvent.change(await screen.findByLabelText(/e-mail/i), { target: { value: "both@example.com" } });
    fireEvent.change(screen.getByLabelText(/Password/), { target: { value: "Correct-Horse-Battery-9" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("heading", { name: "Choose a workspace" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Second Firm/ }));
    expect(
      await screen.findByRole("heading", { name: /^Good (morning|afternoon|evening)/ }),
    ).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/");
    expect(bodies[1]).toMatchObject({ workspace: "second" });
  });
});

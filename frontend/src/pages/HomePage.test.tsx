import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { jsonResponse, makeMe, mockApi, renderRoute } from "../test/utils";

const LIVE = { status: "ok", app: "MigrateCRM", environment: "development" };

describe("HomePage", () => {
  it("greets the user and shows all services operational", async () => {
    mockApi({
      "GET /auth/me": makeMe(),
      "GET /health/live": LIVE,
      "GET /health/ready": { status: "ok", checks: { database: "ok", redis: "ok" } },
    });
    renderRoute("/");
    expect(await screen.findByRole("heading", { name: "Welcome, Alex" })).toBeInTheDocument();
    expect(await screen.findByText("database")).toBeInTheDocument();
    expect(screen.getAllByText("Operational")).toHaveLength(3);
  });

  it("shows a failing dependency from a 503 readiness response", async () => {
    mockApi({
      "GET /auth/me": makeMe(),
      "GET /health/live": LIVE,
      "GET /health/ready": () =>
        jsonResponse({ status: "error", checks: { database: "ok", redis: "error" } }, 503),
    });
    renderRoute("/");
    expect(await screen.findByText("redis")).toBeInTheDocument();
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
  });

  it("shows quick links only for granted permissions", async () => {
    mockApi({
      "GET /auth/me": makeMe({ role: "AUDITOR", permissions: ["dashboard.view", "audit.read"] }),
      "GET /health/live": LIVE,
      "GET /health/ready": { status: "ok", checks: {} },
    });
    renderRoute("/");
    expect(await screen.findByRole("link", { name: /Review every sign-in/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Manage users/ })).not.toBeInTheDocument();
  });
});

describe("routing", () => {
  it("renders the not-found page for unknown routes", async () => {
    mockApi({ "GET /auth/me": makeMe() });
    renderRoute("/no-such-page");
    expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });

  it("shows a retry screen when the API is unreachable", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    renderRoute("/");
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server");
  });
});

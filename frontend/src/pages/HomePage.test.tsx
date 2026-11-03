import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { jsonResponse, renderRoute } from "../test/utils";

function mockApi(ready: { status: number; body: unknown }) {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/health/live")) {
      return jsonResponse({ status: "ok", app: "MigrateCRM", environment: "development" });
    }
    if (url.endsWith("/health/ready")) return jsonResponse(ready.body, ready.status);
    return jsonResponse({ error: { code: "not_found", message: "Not found" } }, 404);
  });
}

describe("HomePage", () => {
  it("shows all services operational", async () => {
    mockApi({ status: 200, body: { status: "ok", checks: { database: "ok", redis: "ok" } } });
    renderRoute("/");
    expect(await screen.findByText("database")).toBeInTheDocument();
    expect(screen.getByText("API (development)")).toBeInTheDocument();
    expect(screen.getAllByText("Operational")).toHaveLength(3);
  });

  it("shows a failing dependency from a 503 readiness response", async () => {
    mockApi({ status: 503, body: { status: "error", checks: { database: "ok", redis: "error" } } });
    renderRoute("/");
    expect(await screen.findByText("redis")).toBeInTheDocument();
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
  });

  it("shows an error when the API is unreachable", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    renderRoute("/");
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server");
  });
});

describe("routing", () => {
  it("renders the not-found page for unknown routes", async () => {
    mockApi({ status: 200, body: { status: "ok", checks: {} } });
    renderRoute("/no-such-page");
    expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });
});

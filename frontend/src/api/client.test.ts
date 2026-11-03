import { describe, expect, it, vi } from "vitest";
import { jsonResponse } from "../test/utils";
import { ApiError, apiRequest, toQueryString } from "./client";

describe("apiRequest", () => {
  it("returns parsed JSON on success and sends same-origin credentials", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ ok: true }));
    await expect(apiRequest("/thing")).resolves.toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/thing",
      expect.objectContaining({ method: "GET", credentials: "same-origin" }),
    );
  });

  it("serialises JSON bodies", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ id: 1 }, 201));
    await apiRequest("/things", { method: "POST", body: { name: "A" } });
    const init = fetchMock.mock.calls[0]![1]!;
    expect(init.body).toBe('{"name":"A"}');
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
  });

  it("maps the server error format to ApiError", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(
        {
          error: {
            code: "validation_error",
            message: "Some fields are invalid.",
            fields: { email: "Invalid email" },
            request_id: "rid-123",
          },
        },
        422,
      ),
    );
    const err = await apiRequest("/x").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({
      status: 422,
      code: "validation_error",
      fields: { email: "Invalid email" },
      requestId: "rid-123",
    });
  });

  it("handles non-JSON error bodies", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("<html>Bad gateway</html>", { status: 502, headers: { "X-Request-ID": "rid-9" } }),
    );
    const err = await apiRequest("/x").catch((e: unknown) => e);
    expect(err).toMatchObject({ status: 502, code: "http_error", requestId: "rid-9" });
  });

  it("reports network failures", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    const err = await apiRequest("/x").catch((e: unknown) => e);
    expect(err).toMatchObject({ status: 0, code: "network_error" });
  });

  it("resolves accepted non-2xx statuses", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ status: "error" }, 503));
    await expect(apiRequest("/health/ready", { acceptStatuses: [503] })).resolves.toEqual({
      status: "error",
    });
  });
});

describe("CSRF header", () => {
  function clearCookies() {
    for (const c of document.cookie.split(";")) {
      const name = c.split("=")[0]?.trim();
      if (name) document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
    }
  }

  it("sends the crm_csrf cookie value on unsafe methods only", async () => {
    clearCookies();
    document.cookie = "other=1; path=/";
    document.cookie = "crm_csrf=tok%3Den123; path=/";
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () => jsonResponse({}));
    await apiRequest("/x", { method: "POST", body: {} });
    await apiRequest("/x");
    const postHeaders = fetchMock.mock.calls[0]![1]!.headers as Record<string, string>;
    const getHeaders = fetchMock.mock.calls[1]![1]!.headers as Record<string, string>;
    expect(postHeaders["X-CSRF-Token"]).toBe("tok=en123");
    expect(getHeaders["X-CSRF-Token"]).toBeUndefined();
    clearCookies();
  });

  it("omits the header when there is no CSRF cookie", async () => {
    clearCookies();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({}));
    await apiRequest("/x", { method: "DELETE" });
    expect((fetchMock.mock.calls[0]![1]!.headers as Record<string, string>)["X-CSRF-Token"]).toBeUndefined();
  });
});

describe("toQueryString", () => {
  it("skips empty values", () => {
    expect(toQueryString({ a: 1, b: "", c: undefined, d: null, e: false, q: "a b" })).toBe(
      "?a=1&e=false&q=a+b",
    );
    expect(toQueryString({})).toBe("");
  });
});

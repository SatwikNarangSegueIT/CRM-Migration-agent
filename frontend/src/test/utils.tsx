import { QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { vi } from "vitest";
import type { MeResponse } from "../api/auth";
import type { Role } from "../api/types";
import { AuthProvider } from "../auth/AuthProvider";
import { ToastProvider } from "../components/ui";
import { createQueryClient } from "../queryClient";
import { routes } from "../routes";

export function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

export function errorResponse(
  status: number,
  code: string,
  message = code,
  fields: Record<string, string> = {},
) {
  return jsonResponse({ error: { code, message, fields, request_id: "rid-test" } }, status);
}

type Handler = (init: RequestInit & { url: string }) => Response | Promise<Response>;

/**
 * Mock fetch with handlers keyed by "METHOD /path" (path relative to /api/v1, without query string).
 * Unmatched requests return 404. Returns the spy so tests can inspect calls.
 */
export function mockApi(handlers: Record<string, Handler | unknown>) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init = {}) => {
    const url = String(input);
    const path = url.replace(/^\/api\/v1/, "").split("?")[0];
    const key = `${(init.method ?? "GET").toUpperCase()} ${path}`;
    if (!(key in handlers)) return errorResponse(404, "not_found", `No mock for ${key}`);
    const handler = handlers[key];
    if (typeof handler === "function") return (handler as Handler)({ ...init, url });
    return jsonResponse(handler);
  });
}

export const ALL_STAFF_PERMISSIONS = ["dashboard.view", "user.manage", "audit.read"];

export function makeMe(
  overrides: {
    role?: Role;
    is_staff?: boolean;
    permissions?: string[];
    mfa_verified?: boolean;
    mfa_setup_required?: boolean;
    mfa_enabled?: boolean;
    id?: string;
    name?: string;
  } = {},
): MeResponse {
  const role = overrides.role ?? "ADMIN";
  const verified = overrides.mfa_verified ?? true;
  return {
    user: {
      id: overrides.id ?? "u-admin",
      email: "admin@demo.example.com",
      name: overrides.name ?? "Alex Admin",
      role,
      role_label: role === "CLIENT" ? "Client" : role === "AUDITOR" ? "Auditor (read-only)" : "Administrator",
      is_staff: overrides.is_staff ?? role !== "CLIENT",
      title: null,
      mara_number: null,
      mfa_enabled: overrides.mfa_enabled ?? false,
    },
    session: {
      mfa_verified: verified,
      mfa_setup_required: overrides.mfa_setup_required ?? false,
      expires_at: "2030-01-01T00:00:00Z",
      recovery_codes_remaining: null,
    },
    permissions: verified
      ? Object.fromEntries((overrides.permissions ?? ALL_STAFF_PERMISSIONS).map((p) => [p, "all"]))
      : {},
  };
}

export function renderRoute(path: string) {
  const queryClient = createQueryClient();
  queryClient.setDefaultOptions({ queries: { retry: false, staleTime: 0 } });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ToastProvider>
          <RouterProvider router={router} />
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>,
  );
  return { ...utils, router, queryClient };
}

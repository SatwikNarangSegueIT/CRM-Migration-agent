import { QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { vi } from "vitest";
import type { MeResponse } from "../api/auth";
import type { ObjectAccess } from "../api/types";
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

function matches(pattern: string, key: string): boolean {
  if (!pattern.includes("*")) return pattern === key;
  const escape = (part: string) => part.replace(/[.+?^$|()[\]{}\\]/g, "\\$&");
  const re = new RegExp("^" + pattern.split("*").map(escape).join("[^/]+") + "$");
  return re.test(key);
}

/**
 * Mock fetch with handlers keyed by "METHOD /path" (path relative to /api/v1, without query string).
 * A "*" matches one path segment, e.g. "POST /objects/{star}/records/query" with {star} written as an asterisk.
 * Exact keys win over patterns.
 * Unmatched requests return 404. Returns the spy so tests can inspect calls.
 */
export function mockApi(handlers: Record<string, Handler | unknown>) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init = {}) => {
    const url = String(input);
    const path = url.replace(/^\/api\/v1/, "").split("?")[0];
    const key = `${(init.method ?? "GET").toUpperCase()} ${path}`;
    const match = key in handlers ? key : Object.keys(handlers).find((k) => matches(k, key));
    if (match === undefined) return errorResponse(404, "not_found", `No mock for ${key}`);
    const handler = handlers[match];
    if (typeof handler === "function") return (handler as Handler)({ ...init, url });
    return jsonResponse(handler);
  });
}

export const EMPTY_PAGE = { items: [], next_cursor: null, total: 0, total_capped: false };

export const SALES_APP = {
  id: "app-sales",
  key: "sales",
  label: "Sales",
  description: "Leads, accounts, contacts and opportunities.",
  icon: "sales",
  color: "#0176d3",
  tabs: [
    { kind: "home", label: "Home" },
    { kind: "object", object: "lead", label: "Leads", icon: "lead", color: "#f97316" },
    { kind: "object", object: "account", label: "Accounts", icon: "account", color: "#6366f1" },
  ],
};

/** Background requests every staff page makes (apps, notifications, recent items, home cards). */
export function shellHandlers(apps: unknown[] = [SALES_APP]): Record<string, unknown> {
  return {
    "GET /meta/apps": apps,
    "GET /me/notifications": { unread: 0, items: [] },
    "GET /me/recent": [],
    "POST /objects/*/records/query": EMPTY_PAGE,
    "GET /dashboards": [],
  };
}

export const ADMIN_PERMISSIONS = [
  "manage_users",
  "customize_application",
  "manage_profiles_sharing",
  "manage_billing_settings",
  "manage_industry_packs",
  "view_setup",
  "view_audit_log",
  "import_data",
  "export_data",
  "send_mass_email",
  "manage_public_reports",
  "transfer_records",
  "manage_portal_users",
  "api_access",
];

export function makeMe(
  overrides: {
    profile?: string;
    is_staff?: boolean;
    is_system_admin?: boolean;
    permissions?: string[];
    objects?: Record<string, Partial<ObjectAccess>>;
    mfa_verified?: boolean;
    mfa_setup_required?: boolean;
    mfa_enabled?: boolean;
    id?: string;
    name?: string;
  } = {},
): MeResponse {
  const profile = overrides.profile ?? "System Administrator";
  const admin = overrides.is_system_admin ?? profile === "System Administrator";
  const verified = overrides.mfa_verified ?? true;
  const none = { read: false, create: false, edit: false, delete: false, view_all: false, modify_all: false };
  return {
    user: {
      id: overrides.id ?? "u-admin",
      email: "admin@demo.example.com",
      name: overrides.name ?? "Alex Admin",
      profile: { id: `p-${profile}`, name: profile },
      role: null,
      is_staff: overrides.is_staff ?? profile !== "Customer Portal User",
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
    system_permissions: verified ? (overrides.permissions ?? (admin ? ADMIN_PERMISSIONS : [])) : [],
    object_permissions: verified
      ? Object.fromEntries(Object.entries(overrides.objects ?? {}).map(([k, v]) => [k, { ...none, ...v }]))
      : {},
    is_system_admin: verified && admin,
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

// Automated accessibility checks (WCAG 2.1 A/AA rules from axe-core) on the main screens.
// jsdom can't compute layout, so colour-contrast is checked separately in the browser e2e run.
import { screen } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it } from "vitest";
import { EMPTY_PAGE, errorResponse, makeMe, mockApi, renderRoute, shellHandlers } from "./utils";

async function violations(): Promise<string[]> {
  const result = await axe.run(document.body, {
    runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
    rules: { "color-contrast": { enabled: false } },
  });
  return result.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.length})`);
}

const field = (api_name: string, label: string, type = "text", extra: Record<string, unknown> = {}) => ({
  api_name,
  label,
  type,
  help_text: null,
  required: false,
  is_unique: false,
  external_id: false,
  filterable: true,
  sortable: true,
  searchable: false,
  track_history: false,
  is_custom: false,
  is_standard: true,
  is_system: api_name === "name" || api_name === "owner_id",
  is_readonly: false,
  indexed: false,
  default_value: null,
  default_access: "edit",
  access: "edit",
  options: {},
  ...extra,
});

const LEAD = {
  api_name: "lead",
  label: "Lead",
  plural_label: "Leads",
  description: null,
  icon: "lead",
  color: "#f97316",
  is_custom: false,
  pack_key: null,
  is_detail_only: false,
  searchable: true,
  allow_reports: true,
  access: { read: true, create: true, edit: true, delete: true, view_all: true, modify_all: true },
  name_field_type: "text",
  name_label: "Name",
  name_format: null,
  track_history: true,
  allow_activities: false,
  allow_files: false,
  allow_notes: false,
  allow_queues: false,
  show_in_portal: false,
  fields: {
    name: field("name", "Name"),
    company: field("company", "Company"),
    status: field("status", "Status", "picklist", {
      options: {
        is_path: true,
        values: [
          { value: "New", label: "New", active: true },
          { value: "Contacted", label: "Contacted", active: true },
        ],
      },
    }),
    owner_id: field("owner_id", "Owner", "owner"),
  },
  page_layout: [{ label: "Lead Information", columns: 2, fields: ["name", "company", "status", "owner_id"] }],
  compact_layout: ["company", "status"],
  list_columns: ["name", "company", "status"],
  related_lists: [],
  activity_objects: [],
  path_field: "status",
  actions: [],
  list_views: [],
};

const RECORD = {
  id: "l1",
  object: "lead",
  name: "Ada Lovelace",
  record_number: null,
  owner: { id: "u-admin", name: "Alex Admin", type: "user" },
  created_at: "2026-11-01T00:00:00Z",
  created_by: null,
  updated_at: "2026-11-01T00:00:00Z",
  updated_by: null,
  version: 1,
  is_deleted: false,
  fields: { company: "Analytical Engines", status: "New" },
  display: {},
  access: { edit: true, delete: true },
  actions: [],
};

const VIEW = {
  id: "v1",
  object_api_name: "lead",
  name: "All Leads",
  key: "lead_all",
  visibility: "public",
  shared_profile_ids: [],
  shared_role_ids: [],
  scope: "all",
  columns: ["name", "company", "status"],
  filters: {},
  sort: [],
  kanban_field: null,
  is_mine: false,
  can_edit: true,
};

describe("accessibility (axe-core, WCAG 2.1 AA)", () => {
  it("sign-in page", async () => {
    mockApi({
      "GET /auth/me": () => errorResponse(401, "unauthenticated"),
      "GET /public/branding": { name: "Meridian CRM", primary_color: "#0176d3", logo_url: null },
    });
    renderRoute("/login");
    await screen.findByRole("button", { name: /sign in/i });
    expect(await violations()).toEqual([]);
  });

  it("home page", async () => {
    mockApi({ ...shellHandlers(), "GET /auth/me": makeMe() });
    renderRoute("/");
    await screen.findByText(/Alex/);
    expect(await violations()).toEqual([]);
  });

  it("list view", async () => {
    mockApi({
      ...shellHandlers(),
      "GET /auth/me": makeMe(),
      "GET /meta/objects/lead": LEAD,
      "GET /objects/lead/list-views": { default_view_id: "v1", views: [VIEW] },
      "POST /objects/lead/records/query": { ...EMPTY_PAGE, items: [RECORD], total: 1 },
    });
    renderRoute("/o/lead");
    await screen.findByRole("link", { name: "Ada Lovelace" });
    expect(await violations()).toEqual([]);
  });

  it("record page", async () => {
    mockApi({
      ...shellHandlers(),
      "GET /auth/me": makeMe(),
      "GET /meta/objects/lead": LEAD,
      "GET /objects/lead/records/l1": RECORD,
      "GET /objects/lead/records/l1/history": [],
    });
    renderRoute("/o/lead/l1");
    await screen.findByRole("heading", { name: "Ada Lovelace" });
    expect(await violations()).toEqual([]);
  });

  it("setup home", async () => {
    mockApi({ ...shellHandlers(), "GET /auth/me": makeMe() });
    renderRoute("/setup");
    await screen.findByRole("heading", { name: "Setup" });
    expect(await violations()).toEqual([]);
  });
});

import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { jsonResponse, makeMe, mockApi, renderRoute, shellHandlers } from "../../test/utils";

const SUMMARY = {
  api_name: "vehicle__c",
  label: "Vehicle",
  plural_label: "Vehicles",
  icon: "custom",
  color: "#6366f1",
  is_custom: true,
  pack_key: null,
  description: null,
  field_count: 3,
  updated_at: "2026-11-01T00:00:00Z",
};

const NAME_FIELD = {
  api_name: "name",
  label: "Vehicle Name",
  type: "text",
  help_text: null,
  required: true,
  is_unique: false,
  external_id: false,
  filterable: true,
  sortable: true,
  searchable: true,
  track_history: false,
  is_custom: false,
  is_standard: true,
  is_system: false,
  is_readonly: false,
  indexed: false,
  default_value: null,
  default_access: "edit",
  access: "edit",
  options: {},
};

const OBJECT = {
  ...SUMMARY,
  id: "obj-1",
  name_field_type: "text",
  name_label: "Vehicle Name",
  name_format: null,
  track_history: true,
  allow_activities: true,
  allow_files: true,
  allow_notes: true,
  searchable: true,
  allow_reports: true,
  show_in_portal: false,
  allow_queues: false,
  is_detail_only: false,
  page_layout: [{ label: "Vehicle Information", columns: 2, fields: ["name"] }],
  compact_layout: ["name"],
  related_lists: [],
  list_columns: ["name"],
  fields: [NAME_FIELD],
  deleted_fields: [],
  field_types: ["text", "number", "picklist", "lookup", "auto_number"],
};

describe("Object Manager", () => {
  it("lists objects and opens one", async () => {
    mockApi({
      ...shellHandlers(),
      "GET /auth/me": makeMe(),
      "GET /setup/objects": [
        SUMMARY,
        { ...SUMMARY, api_name: "account", label: "Account", plural_label: "Accounts", is_custom: false },
      ],
      "GET /setup/objects/vehicle__c": OBJECT,
    });
    renderRoute("/setup/objects");
    const link = await screen.findByRole("link", { name: "Vehicle" });
    expect(link).toHaveAttribute("href", "/setup/objects/vehicle__c");
    expect(screen.getByText("2 objects • Sorted by Label")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /New Custom Object/ })).toBeInTheDocument();
  });

  it("creates a picklist field with ordered values", async () => {
    let body: Record<string, unknown> | null = null;
    mockApi({
      ...shellHandlers(),
      "GET /auth/me": makeMe(),
      "GET /setup/objects": [SUMMARY],
      "GET /setup/objects/vehicle__c": OBJECT,
      "POST /setup/objects/vehicle__c/fields": (init: RequestInit) => {
        body = JSON.parse(String(init.body)) as Record<string, unknown>;
        return jsonResponse(OBJECT);
      },
    });
    renderRoute("/setup/objects/vehicle__c");
    fireEvent.click(await screen.findByRole("button", { name: /New Field/ }));
    const dialog = await screen.findByRole("dialog", { name: "New field on Vehicle" });
    const auto = within(dialog).getByLabelText(/Data type/);
    expect(within(auto).queryByText("Auto Number")).not.toBeInTheDocument();
    fireEvent.change(auto, { target: { value: "picklist" } });
    fireEvent.change(within(dialog).getByLabelText(/Field label/), { target: { value: "Fuel" } });
    fireEvent.change(within(dialog).getByLabelText(/Add values/), {
      target: { value: "Petrol\nDiesel\npetrol" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Add" }));
    fireEvent.click(within(dialog).getByLabelText("Move Diesel up"));
    fireEvent.click(within(dialog).getByLabelText("Diesel default"));
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(body).not.toBeNull());
    expect(body).toMatchObject({
      type: "picklist",
      label: "Fuel",
      default_access: "hidden",
      options: {
        is_path: false,
        values: [
          { value: "Diesel", label: "Diesel", active: true, default: true },
          { value: "Petrol", label: "Petrol", active: true },
        ],
      },
    });
  });

  it("is read-only without Customize Application", async () => {
    mockApi({
      ...shellHandlers(),
      "GET /auth/me": makeMe({
        profile: "Read Only (Auditor)",
        permissions: ["view_setup", "view_audit_log", "export_data"],
      }),
      "GET /setup/objects": [SUMMARY],
      "GET /setup/objects/vehicle__c": OBJECT,
    });
    renderRoute("/setup/objects/vehicle__c");
    expect(await screen.findByText("Vehicle Name")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /New Field/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
  });
});

describe("settings", () => {
  const SETTINGS = {
    billing: {
      invoice_prefix: "INV-",
      invoice_number_digits: 6,
      payment_terms_days: 14,
      invoice_footer: "",
      bank_details: "",
      gst_registered: true,
    },
    case_sla: {
      Critical: { first_response_hours: 1, resolution_hours: 8 },
      High: { first_response_hours: 4, resolution_hours: 24 },
      Medium: { first_response_hours: 8, resolution_hours: 72 },
      Low: { first_response_hours: 24, resolution_hours: 120 },
    },
    service: { web_queue_id: null, web_to_case_enabled: true, web_to_lead_enabled: true },
  };

  it("saves billing settings with numbers as numbers", async () => {
    let saved: unknown = null;
    mockApi({
      ...shellHandlers(),
      "GET /auth/me": makeMe(),
      "GET /setup/settings": SETTINGS,
      "PUT /setup/settings/billing": (init: RequestInit) => {
        saved = JSON.parse(String(init.body));
        return jsonResponse({ ...SETTINGS.billing, payment_terms_days: 30 });
      },
    });
    renderRoute("/setup/settings/billing");
    const terms = await screen.findByLabelText("Payment terms (days)");
    fireEvent.change(terms, { target: { value: "30" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(saved).not.toBeNull());
    expect(saved).toEqual({ value: { ...SETTINGS.billing, payment_terms_days: 30 } });
    expect(await screen.findByText("Invoices saved.")).toBeInTheDocument();
  });

  it("edits SLA hours per priority", async () => {
    let saved: { value: Record<string, unknown> } | null = null;
    mockApi({
      ...shellHandlers(),
      "GET /auth/me": makeMe(),
      "GET /setup/settings": SETTINGS,
      "GET /setup/queues": [],
      "PUT /setup/settings/case_sla": (init: RequestInit) => {
        saved = JSON.parse(String(init.body)) as { value: Record<string, unknown> };
        return jsonResponse(saved.value);
      },
    });
    renderRoute("/setup/settings/service");
    fireEvent.change(await screen.findByLabelText("High resolution hours"), { target: { value: "12" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Save" })[0]!);
    await waitFor(() => expect(saved).not.toBeNull());
    expect(saved!.value.High).toEqual({ first_response_hours: 4, resolution_hours: 12 });
  });

  it("shows billing settings read-only without Manage Billing Settings", async () => {
    mockApi({
      ...shellHandlers(),
      "GET /auth/me": makeMe({ profile: "Read Only (Auditor)", permissions: ["view_setup"] }),
      "GET /setup/settings": SETTINGS,
    });
    renderRoute("/setup/settings/billing");
    expect(await screen.findByLabelText("Payment terms (days)")).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
  });

  it("returns not found for an unknown section", async () => {
    mockApi({ ...shellHandlers(), "GET /auth/me": makeMe() });
    renderRoute("/setup/settings/nope");
    expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });
});

describe("industry packs", () => {
  const PACK = {
    key: "migration_agency",
    name: "Migration Agency (Australia)",
    version: "1.0.0",
    description: "Matters, visa types and client account.",
    region: "AU",
    installed_version: null,
    is_enabled: false,
    upgrade_available: false,
    installed_at: null,
    custom_permissions: [],
    contents: { objects: 6, apps: 1, profiles: 6 },
  };

  it("installs a pack after confirmation", async () => {
    let installed = false;
    mockApi({
      ...shellHandlers(),
      "GET /auth/me": makeMe(),
      "GET /setup/packs": () =>
        jsonResponse([installed ? { ...PACK, installed_version: "1.0.0", is_enabled: true } : PACK]),
      "GET /setup/profiles": [],
      "POST /setup/packs/migration_agency/install": () => {
        installed = true;
        return jsonResponse([{ ...PACK, installed_version: "1.0.0", is_enabled: true }]);
      },
    });
    renderRoute("/setup/packs");
    expect(await screen.findByText("6 objects, 1 app, 6 profiles", { exact: false })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Install" }));
    const dialog = await screen.findByRole("dialog", { name: /Install Migration Agency/ });
    fireEvent.click(within(dialog).getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Migration Agency (Australia) installed.")).toBeInTheDocument();
    expect(installed).toBe(true);
    expect(await screen.findByText("Enabled")).toBeInTheDocument();
  });
});

describe("app manager", () => {
  it("adds an object tab and saves the app", async () => {
    let body: Record<string, unknown> | null = null;
    mockApi({
      ...shellHandlers(),
      "GET /auth/me": makeMe(),
      "GET /setup/apps": [],
      "GET /setup/objects": [SUMMARY],
      "GET /setup/profiles": [],
      "POST /setup/apps": (init: RequestInit) => {
        body = JSON.parse(String(init.body)) as Record<string, unknown>;
        return jsonResponse({ ...body, id: "a1", key: "fleet", pack_key: null });
      },
    });
    renderRoute("/setup/apps");
    fireEvent.click(await screen.findByRole("button", { name: /New App/ }));
    const dialog = await screen.findByRole("dialog", { name: "New app" });
    fireEvent.change(within(dialog).getByLabelText(/App name/), { target: { value: "Fleet" } });
    await within(dialog).findByRole("option", { name: "Vehicles" });
    fireEvent.change(within(dialog).getByLabelText("Add tab"), { target: { value: "object:vehicle__c" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Add" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(body).not.toBeNull());
    expect(body).toMatchObject({
      label: "Fleet",
      is_active: true,
      tabs: [{ kind: "home" }, { kind: "object", object: "vehicle__c" }],
      profile_ids: [],
    });
  });
});

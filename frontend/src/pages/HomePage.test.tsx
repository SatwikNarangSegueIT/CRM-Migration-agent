import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  EMPTY_PAGE,
  jsonResponse,
  makeMe,
  mockApi,
  renderRoute,
  SALES_APP,
  shellHandlers,
} from "../test/utils";

const LEAD_META = {
  api_name: "lead",
  label: "Lead",
  plural_label: "Leads",
  icon: "lead",
  color: "#f97316",
  fields: {
    company: { api_name: "company", label: "Company", type: "text", options: {} },
    status: { api_name: "status", label: "Status", type: "picklist", options: { values: [] } },
  },
};

function lead(id: string, name: string, company: string) {
  return {
    id,
    object: "lead",
    name,
    record_number: null,
    owner: null,
    created_at: "2026-11-01T00:00:00Z",
    created_by: null,
    updated_at: "2026-11-01T00:00:00Z",
    updated_by: null,
    version: 1,
    is_deleted: false,
    fields: { company, status: "New" },
    display: {},
    access: { edit: true, delete: false },
  };
}

describe("HomePage", () => {
  it("greets the user and shows cards only for readable objects", async () => {
    mockApi({
      ...shellHandlers(),
      "GET /auth/me": makeMe({
        profile: "Sales Representative",
        objects: { lead: { read: true }, task: { read: true } },
      }),
      "GET /meta/objects/lead": LEAD_META,
      "POST /objects/lead/records/query": {
        ...EMPTY_PAGE,
        items: [lead("l1", "Ada Lovelace", "Analytical Engines")],
        total: 1,
      },
    });
    renderRoute("/");
    expect(
      await screen.findByRole("heading", { name: /^Good (morning|afternoon|evening), Alex$/ }),
    ).toBeInTheDocument();
    const leads = (await screen.findByText("My Leads")).closest("section") ?? document.body;
    expect(await within(leads as HTMLElement).findByRole("link", { name: "Ada Lovelace" })).toHaveAttribute(
      "href",
      "/o/lead/l1",
    );
    expect(await screen.findByText("Analytical Engines")).toBeInTheDocument();
    expect(screen.getByText("My Tasks")).toBeInTheDocument();
    // No opportunity or case access: those cards and starters are hidden.
    expect(screen.queryByText("My Open Opportunities")).not.toBeInTheDocument();
    expect(screen.queryByText("My Open Cases")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Add a lead/ })).toHaveAttribute("href", "/o/lead");
    expect(screen.queryByRole("link", { name: /Track an opportunity/ })).not.toBeInTheDocument();
  });

  it("shows app-specific content on an app home page", async () => {
    const service = {
      ...SALES_APP,
      id: "app-service",
      key: "service",
      label: "Service",
      description: "Cases and queues.",
      tabs: [{ kind: "home", label: "Home" }],
    };
    mockApi({
      ...shellHandlers([SALES_APP, service]),
      "GET /auth/me": makeMe({
        profile: "Service Agent",
        objects: { case: { read: true, create: true, edit: true } },
      }),
      "GET /meta/objects/case": {
        ...LEAD_META,
        api_name: "case",
        label: "Case",
        plural_label: "Cases",
        fields: {},
      },
    });
    renderRoute("/app/service");
    expect(await screen.findByText("Cases and queues.")).toBeInTheDocument();
    expect(await screen.findByText("Queue: waiting to be accepted")).toBeInTheDocument();
    expect(screen.getByText("My Open Cases")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Work the queue/ })).toHaveAttribute(
      "href",
      "/o/case?scope=queue",
    );
  });

  it("shows an error inside a card when its records cannot be loaded", async () => {
    mockApi({
      ...shellHandlers(),
      "GET /auth/me": makeMe({ profile: "Sales Representative", objects: { lead: { read: true } } }),
      "GET /meta/objects/lead": LEAD_META,
      "POST /objects/lead/records/query": () =>
        jsonResponse({ error: { code: "internal_error", message: "Something broke.", fields: {} } }, 500),
    });
    renderRoute("/");
    expect(await screen.findByText("Something broke.", {}, { timeout: 4000 })).toBeInTheDocument();
  });
});

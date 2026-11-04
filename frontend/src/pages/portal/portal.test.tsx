import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { errorResponse, jsonResponse, makeMe, mockApi, renderRoute } from "../../test/utils";

const CLIENT = makeMe({ profile: "Customer Portal User", name: "Priya Client", id: "u-client" });

const PORTAL_ME = {
  contact: { id: "c1", name: "Priya Client", email: "priya@example.com", phone: null },
  account: { id: "a1", name: "Acme Pty Ltd" },
  objects: [
    { api_name: "case", label: "Case", plural_label: "Cases", icon: "case", can_create: true },
    {
      api_name: "service_agreement",
      label: "Service Agreement",
      plural_label: "Service Agreements",
      icon: "agreement",
      can_create: false,
    },
  ],
  counts: { case: 2 },
  branding: {},
};

const CASE_META = {
  api_name: "case",
  label: "Case",
  plural_label: "Cases",
  icon: "case",
  color: "#ef4444",
  name_label: "Case Number",
  fields: {
    subject: { api_name: "subject", label: "Subject", type: "text", options: {} },
    status: {
      api_name: "status",
      label: "Status",
      type: "picklist",
      options: { values: [{ value: "New", label: "New", active: true }] },
    },
    priority: {
      api_name: "priority",
      label: "Priority",
      type: "picklist",
      options: {
        values: [
          { value: "High", label: "High", active: true },
          { value: "Low", label: "Low", active: true },
        ],
      },
    },
  },
  page_layout: [{ label: "Case Information", columns: 2, fields: ["subject", "status"] }],
  compact_layout: ["status"],
  list_columns: ["subject", "status"],
  path_field: "status",
};

function record(object: string, id: string, name: string, fields: Record<string, unknown>) {
  return {
    id,
    object,
    name,
    record_number: name,
    owner: null,
    created_at: "2026-11-01T00:00:00Z",
    created_by: { id: "u-client", name: "Priya Client" },
    updated_at: "2026-11-01T00:00:00Z",
    updated_by: null,
    version: 1,
    is_deleted: false,
    fields,
    display: {},
    access: { edit: false, delete: false },
  };
}

describe("customer portal", () => {
  it("shows the customer's areas and record counts", async () => {
    mockApi({ "GET /auth/me": CLIENT, "GET /portal/me": PORTAL_ME });
    renderRoute("/portal");
    expect(await screen.findByRole("heading", { name: "Hello, Priya" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Cases\s*2 total/ })).toHaveAttribute("href", "/portal/o/case");
    expect(screen.getByRole("link", { name: /Service Agreements/ })).toHaveAttribute(
      "href",
      "/portal/o/service_agreement",
    );
    expect(screen.getByRole("link", { name: /Get help/ })).toHaveAttribute("href", "/portal/cases/new");
    expect(screen.getByText(/Acme Pty Ltd/)).toBeInTheDocument();
  });

  it("lists records with the object's columns", async () => {
    mockApi({
      "GET /auth/me": CLIENT,
      "GET /portal/me": PORTAL_ME,
      "GET /portal/objects/case/describe": CASE_META,
      "GET /portal/objects/case/records": {
        items: [record("case", "k1", "CASE-00001", { subject: "Login broken", status: "New" })],
        next_cursor: null,
        total: 1,
      },
    });
    renderRoute("/portal/o/case");
    expect(await screen.findByRole("link", { name: "CASE-00001" })).toHaveAttribute(
      "href",
      "/portal/o/case/k1",
    );
    const table = screen.getByRole("table");
    expect(within(table).getByText("Subject")).toBeInTheDocument();
    expect(within(table).getByText("Login broken")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /New case/ })).toBeInTheDocument();
  });

  it("shows a record with its conversation and posts a message", async () => {
    let posted: unknown = null;
    mockApi({
      "GET /auth/me": CLIENT,
      "GET /portal/objects/case/describe": CASE_META,
      "GET /portal/objects/case/records/k1": {
        ...record("case", "k1", "CASE-00001", { subject: "Login broken", status: "New" }),
        actions: [],
        timeline: { note: [record("note", "n1", "Reply", { body: "We're on it" })], file: [] },
        related: [],
      },
      "POST /portal/objects/case/records/k1/comments": (init: RequestInit) => {
        posted = JSON.parse(String(init.body));
        return jsonResponse(record("note", "n2", "Comment", { body: "Thanks!" }));
      },
    });
    renderRoute("/portal/o/case/k1");
    expect(await screen.findByRole("heading", { name: "CASE-00001" })).toBeInTheDocument();
    expect(screen.getByText("Login broken")).toBeInTheDocument();
    expect(screen.getByText("We're on it")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Download PDF/ })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Add a message"), { target: { value: "Thanks!" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(posted).toEqual({ body: "Thanks!" }));
  });

  it("leaves empty fields and staff bookkeeping off a record", async () => {
    mockApi({
      "GET /auth/me": CLIENT,
      "GET /portal/objects/case/describe": {
        ...CASE_META,
        page_layout: [
          { label: "Case Information", columns: 2, fields: ["subject", "status", "priority"] },
          { label: "System Information", columns: 2, fields: ["created_by", "updated_at"] },
        ],
      },
      "GET /portal/objects/case/records/k1": {
        ...record("case", "k1", "CASE-00001", { subject: "Login broken", status: "New", priority: null }),
        actions: [],
        timeline: { note: [], file: [] },
        related: [],
      },
    });
    renderRoute("/portal/o/case/k1");
    expect(await screen.findByText("Login broken")).toBeInTheDocument();
    expect(screen.queryByText("Priority")).not.toBeInTheDocument();
    expect(screen.queryByText("null")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "System Information" })).not.toBeInTheDocument();
  });

  it("signs a service agreement with full name and acceptance", async () => {
    let payload: unknown = null;
    mockApi({
      "GET /auth/me": CLIENT,
      "GET /portal/objects/service_agreement/describe": {
        ...CASE_META,
        api_name: "service_agreement",
        label: "Service Agreement",
        plural_label: "Service Agreements",
        fields: {},
        page_layout: [],
        compact_layout: [],
      },
      "GET /portal/objects/service_agreement/records/sa1": {
        ...record("service_agreement", "sa1", "SA-0001", { status: "Sent" }),
        actions: [{ name: "sign", label: "Sign agreement" }],
        timeline: {},
        related: [],
      },
      "POST /portal/objects/service_agreement/records/sa1/actions/sign": (init: RequestInit) => {
        payload = JSON.parse(String(init.body));
        return jsonResponse({ ok: true });
      },
    });
    renderRoute("/portal/o/service_agreement/sa1");
    fireEvent.click(await screen.findByRole("button", { name: "Sign agreement" }));
    const dialog = await screen.findByRole("dialog", { name: "Sign agreement" });
    const sign = within(dialog).getByRole("button", { name: "Sign" });
    expect(sign).toBeDisabled();
    fireEvent.click(within(dialog).getByLabelText(/I have read and accept/));
    fireEvent.click(sign);
    await waitFor(() => expect(payload).toEqual({ full_name: "Priya Client", accept: true }));
    expect(await screen.findByText("Signed. Thank you.")).toBeInTheDocument();
  });

  it("creates a case and opens it", async () => {
    let body: unknown = null;
    mockApi({
      "GET /auth/me": CLIENT,
      "GET /portal/objects/case/describe": CASE_META,
      "POST /portal/cases": (init: RequestInit) => {
        body = JSON.parse(String(init.body));
        return jsonResponse(record("case", "k9", "CASE-00009", { subject: "Printer jam" }), 201);
      },
      "GET /portal/objects/case/records/k9": {
        ...record("case", "k9", "CASE-00009", { subject: "Printer jam", status: "New" }),
        actions: [],
        timeline: {},
        related: [],
      },
    });
    const { router } = renderRoute("/portal/cases/new");
    fireEvent.change(await screen.findByLabelText(/Subject/), { target: { value: "Printer jam" } });
    await screen.findByRole("option", { name: "High" });
    fireEvent.change(screen.getByLabelText("Priority"), { target: { value: "High" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/portal/o/case/k9"));
    expect(body).toEqual({ subject: "Printer jam", priority: "High" });
  });
});

describe("unsubscribe page", () => {
  it("unsubscribes without signing in", async () => {
    let done = false;
    mockApi({
      "GET /auth/me": () => errorResponse(401, "unauthenticated"),
      "GET /public/unsubscribe/tok123": { email: "priya@example.com", unsubscribed: false, sender: "Acme" },
      "POST /public/unsubscribe/tok123": () => {
        done = true;
        return jsonResponse({ unsubscribed: true });
      },
    });
    renderRoute("/unsubscribe/tok123");
    fireEvent.click(await screen.findByRole("button", { name: "Unsubscribe" }));
    expect(await screen.findByText("You're unsubscribed")).toBeInTheDocument();
    expect(done).toBe(true);
  });

  it("explains an invalid link", async () => {
    mockApi({
      "GET /auth/me": () => errorResponse(401, "unauthenticated"),
      "GET /public/unsubscribe/bad": () => errorResponse(404, "not_found"),
    });
    renderRoute("/unsubscribe/bad");
    expect(await screen.findByText("This link is invalid or has expired.")).toBeInTheDocument();
  });
});

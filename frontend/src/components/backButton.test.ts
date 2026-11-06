import { describe, expect, it } from "vitest";
import { parentPath } from "./AppShell";

describe("Back button target", () => {
  it("is hidden only on Home", () => {
    for (const p of ["/", "/app/legal_practice"]) expect(parentPath(p, "")).toBeNull();
    for (const p of ["/o/contact", "/setup", "/calendar", "/reports", "/dashboards", "/search"])
      expect(parentPath(p, "")).toBe("/");
  });
  it("goes up one level from a subsection", () => {
    expect(parentPath("/o/contact/123", "")).toBe("/o/contact");
    expect(parentPath("/import", "?object=contact")).toBe("/o/contact");
    expect(parentPath("/setup/profiles/9", "")).toBe("/setup/profiles");
    expect(parentPath("/setup/portal-users", "")).toBe("/setup");
    expect(parentPath("/admin/users/5", "")).toBe("/admin/users");
    expect(parentPath("/admin/users", "")).toBe("/setup");
    expect(parentPath("/reports/7", "")).toBe("/reports");
    expect(parentPath("/recycle-bin", "")).toBe("/setup");
  });
});

describe("Portal Back button target", () => {
  it("goes to the list, then portal home", async () => {
    const { portalParent } = await import("./PortalLayout");
    expect(portalParent("/portal")).toBeNull();
    expect(portalParent("/portal/o/case/1")).toBe("/portal/o/case");
    expect(portalParent("/portal/o/case")).toBe("/portal");
    expect(portalParent("/portal/account")).toBe("/portal");
  });
});

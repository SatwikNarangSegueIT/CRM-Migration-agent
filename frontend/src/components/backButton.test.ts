import { describe, expect, it } from "vitest";
import { parentPath } from "./AppShell";

describe("Back button target", () => {
  it("is hidden on the main sections", () => {
    for (const p of [
      "/",
      "/app/legal_practice",
      "/o/contact",
      "/setup",
      "/calendar",
      "/reports",
      "/dashboards",
    ])
      expect(parentPath(p, "")).toBeNull();
  });
  it("goes up one level from a subsection", () => {
    expect(parentPath("/o/contact/123", "")).toBe("/o/contact");
    expect(parentPath("/import", "?object=contact")).toBe("/o/contact");
    expect(parentPath("/setup/profiles/9", "")).toBe("/setup/profiles");
    expect(parentPath("/setup/portal-users", "")).toBe("/setup");
    expect(parentPath("/admin/users/5", "")).toBe("/admin/users");
    expect(parentPath("/admin/users", "")).toBe("/setup");
    expect(parentPath("/reports/7", "")).toBe("/reports");
  });
});

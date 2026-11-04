import { describe, expect, it } from "vitest";
import type { AppInfo } from "./api/types";
import { currentApp, rememberApp } from "./navigation";

const app = (key: string, objects: string[], is_primary = false) =>
  ({
    key,
    is_primary,
    tabs: objects.map((object) => ({ kind: "object", object, label: object })),
  }) as unknown as AppInfo;

describe("currentApp", () => {
  const legal = app("legal_practice", ["legal_matter", "contact"], true);
  const analytics = app("analytics", []);

  it("picks the app with a tab for the page", () => {
    expect(currentApp([analytics, legal], "/o/legal_matter/1", "")?.key).toBe("legal_practice");
  });

  it("keeps the last app's tabs on a record no tab leads to", () => {
    rememberApp("legal_practice");
    expect(currentApp([analytics, legal], "/o/conflict_check/1", "")?.key).toBe("legal_practice");
  });
});

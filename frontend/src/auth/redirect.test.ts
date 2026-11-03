import { describe, expect, it } from "vitest";
import { loginPath, safeNext } from "./redirect";

describe("safeNext", () => {
  it("accepts in-app paths", () => {
    expect(safeNext("/admin/users?page=2")).toBe("/admin/users?page=2");
  });
  it.each([null, "", "https://evil.example", "//evil.example", "/\\evil.example", "javascript:alert(1)"])(
    "rejects %s",
    (value) => {
      expect(safeNext(value)).toBe("/");
    },
  );
  it("builds login paths", () => {
    expect(loginPath("/")).toBe("/login");
    expect(loginPath("/admin/users")).toBe("/login?next=%2Fadmin%2Fusers");
  });
});

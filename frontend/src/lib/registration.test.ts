import { describe, expect, it } from "vitest";
import { registrationField } from "./registration";

describe("registrationField", () => {
  it("asks each profession for its own registration number", () => {
    expect(registrationField("migration")?.label).toBe("MARN");
    expect(registrationField("accounting")?.label).toBe("Tax agent number");
    expect(registrationField("lending")?.label).toBe("Credit representative number");
    expect(registrationField("legal")?.label).toBe("Practising certificate number");
    expect(registrationField("legal")?.digitsOnly).toBe(false);
  });

  it("asks for none in a general CRM", () => {
    expect(registrationField(null)).toBeNull();
    expect(registrationField(undefined)).toBeNull();
  });
});

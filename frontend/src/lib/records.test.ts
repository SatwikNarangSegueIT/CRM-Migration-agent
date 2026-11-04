import { describe, expect, it } from "vitest";
import type { ObjectDescribe } from "../api/types";
import { editableFields } from "./records";

const field = (api_name: string, extra: Record<string, unknown> = {}) => ({
  api_name,
  label: api_name,
  type: "text",
  help_text: null,
  required: false,
  is_system: api_name === "name",
  is_readonly: false,
  access: "edit",
  options: {},
  ...extra,
});

function meta(fields: ReturnType<typeof field>[], layout: string[]): ObjectDescribe {
  return {
    api_name: "matter",
    name_field_type: "text",
    fields: Object.fromEntries(fields.map((f) => [f.api_name, f])),
    page_layout: [{ label: "Matter", columns: 2, fields: layout }],
  } as unknown as ObjectDescribe;
}

describe("editableFields", () => {
  it("leaves out fields filled in later when creating, but not when editing", () => {
    const m = meta(
      [
        field("name", { required: true }),
        field("client"),
        field("stage", { options: { hide_on_create: true } }),
      ],
      ["name", "client", "stage"],
    );
    expect(editableFields(m, true)).toEqual(["name", "client"]);
    expect(editableFields(m, false)).toEqual(["name", "client", "stage"]);
  });

  it("doesn't ask for a name the layout doesn't show (the system names the record)", () => {
    const m = meta([field("name", { required: true }), field("contact", { required: true })], ["contact"]);
    expect(editableFields(m, true)).toEqual(["contact"]);
  });
});

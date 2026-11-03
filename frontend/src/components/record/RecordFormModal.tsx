import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState, type FormEvent } from "react";
import { ApiError, errorMessage } from "../../api/client";
import { recordsApi } from "../../api/records";
import type { ObjectDescribe, RecordData } from "../../api/types";
import { editableFields } from "../../lib/records";
import { Alert, Button, FormField } from "../ui";
import { Modal } from "../ui/Modal";
import { FieldInput } from "./FieldInput";

function initialValues(
  meta: ObjectDescribe,
  record: RecordData | null,
  defaults: Record<string, unknown>,
): Record<string, unknown> {
  const values: Record<string, unknown> = {};
  for (const f of Object.values(meta.fields)) {
    if (record)
      values[f.api_name] = f.api_name === "name" ? record.name : (record.fields[f.api_name] ?? null);
    else if (f.default_value !== null && f.default_value !== undefined) {
      values[f.api_name] =
        f.default_value === "today"
          ? new Date().toISOString().slice(0, 10)
          : f.default_value === "now"
            ? null
            : f.default_value;
    }
    if (!record && f.type === "picklist") {
      const def = f.options.values?.find((v) => v.default && v.active);
      if (def && values[f.api_name] === undefined) values[f.api_name] = def.value;
    }
  }
  return { ...values, ...defaults };
}

/** Create or edit any record. Sections come from the object's page layout; only editable fields show. */
export function RecordFormModal({
  meta,
  record,
  defaults = {},
  defaultNames = {},
  open,
  onClose,
  onSaved,
}: {
  meta: ObjectDescribe;
  record: RecordData | null;
  defaults?: Record<string, unknown>;
  /** Display names for prefilled lookups, e.g. the parent record of a related list. */
  defaultNames?: Record<string, string>;
  open: boolean;
  onClose: () => void;
  onSaved: (record: RecordData) => void;
}) {
  const queryClient = useQueryClient();
  const creating = record === null;
  const [values, setValues] = useState(() => initialValues(meta, record, defaults));
  const [names, setNames] = useState<Record<string, string>>(() => ({
    ...Object.fromEntries(Object.entries(record?.display ?? {}).map(([k, v]) => [k, v.name])),
    ...defaultNames,
  }));
  const editable = useMemo(() => editableFields(meta, creating), [meta, creating]);
  const sections = useMemo(() => {
    const used = new Set<string>();
    const out = meta.page_layout
      .map((s) => {
        const fields = s.fields.filter((f) => editable.includes(f));
        fields.forEach((f) => used.add(f));
        return { ...s, fields };
      })
      .filter((s) => s.fields.length > 0);
    const rest = editable.filter((f) => !used.has(f));
    if (rest.length) out.push({ label: "Additional Information", columns: 2, fields: rest });
    return out;
  }, [meta, editable]);

  const save = useMutation({
    mutationFn: () => {
      const fields: Record<string, unknown> = {};
      let name: string | undefined;
      for (const api of editable) {
        const v = values[api];
        if (api === "name") {
          if (creating || v !== record?.name) name = (v as string) ?? "";
          continue;
        }
        const before = record ? (record.fields[api] ?? null) : null;
        if (
          creating
            ? v !== undefined && v !== null && v !== ""
            : JSON.stringify(v ?? null) !== JSON.stringify(before)
        ) {
          fields[api] = v === "" ? null : v;
        }
      }
      for (const [k, v] of Object.entries(defaults))
        if (creating && !(k in fields) && k !== "name") fields[k] = v;
      return creating
        ? recordsApi.create(meta.api_name, { name, fields })
        : recordsApi.update(meta.api_name, record.id, { version: record.version, name, fields });
    },
    onSuccess: (saved) => {
      void queryClient.invalidateQueries({ queryKey: ["records", meta.api_name] });
      void queryClient.invalidateQueries({ queryKey: ["record"] });
      void queryClient.invalidateQueries({ queryKey: ["related"] });
      onSaved(saved);
    },
  });
  const err = save.error instanceof ApiError ? save.error : null;
  const fieldErrors = err?.fields ?? {};
  const unmapped =
    err && !Object.keys(fieldErrors).some((k) => editable.includes(k)) ? errorMessage(err) : null;
  const conflict = err?.status === 409 && err.code === "stale_version";

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    save.mutate();
  }

  const title = creating ? `New ${meta.label}` : `Edit ${record.name}`;
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      size="lg"
      busy={save.isPending}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={save.isPending}>
            Cancel
          </Button>
          <Button type="submit" form="record-form" loading={save.isPending}>
            Save
          </Button>
        </>
      }
    >
      <form id="record-form" onSubmit={onSubmit} noValidate className="space-y-6">
        {conflict && (
          <Alert tone="warning" title="This record was changed by someone else">
            Close this form and reload the record to see the latest values.
          </Alert>
        )}
        {unmapped && !conflict && <Alert tone="error">{unmapped}</Alert>}
        {sections.map((section) => (
          <fieldset key={section.label}>
            <legend className="mb-3 w-full rounded bg-slate-100 px-3 py-1.5 text-sm font-semibold text-slate-800">
              {section.label}
            </legend>
            <div className={section.columns === 2 ? "grid gap-4 sm:grid-cols-2" : "grid gap-4"}>
              {section.fields.map((api) => {
                const f = meta.fields[api]!;
                const wide = ["long_text", "textarea", "address", "multi_picklist"].includes(f.type);
                return (
                  <div key={api} className={wide && section.columns === 2 ? "sm:col-span-2" : undefined}>
                    <FormField
                      label={f.label}
                      required={f.required || (api === "name" && creating)}
                      hint={f.help_text ?? undefined}
                      error={fieldErrors[api]}
                    >
                      {({ id, describedBy, invalid }) => (
                        <FieldInput
                          id={id}
                          field={f}
                          value={values[api]}
                          displayName={names[api]}
                          invalid={invalid}
                          describedBy={describedBy}
                          onChange={(v) => {
                            setValues((cur) => ({ ...cur, [api]: v }));
                            if (v === null) setNames((n) => ({ ...n, [api]: "" }));
                          }}
                        />
                      )}
                    </FormField>
                  </div>
                );
              })}
            </div>
          </fieldset>
        ))}
      </form>
    </Modal>
  );
}

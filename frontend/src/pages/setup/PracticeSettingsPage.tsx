// Setup → Practice Settings: the profession's own settings (rates, compliance thresholds, due dates and
// reminder lead times), described by each installed pack.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { ApiError, apiRequest, errorMessage } from "../../api/client";
import { useAuth } from "../../auth/context";
import { SettingsIcon } from "../../components/icons";
import { controlClass } from "../../components/record/FieldInput";
import {
  Alert,
  Button,
  Checkbox,
  FormField,
  Input,
  PageHeader,
  Spinner,
  useToast,
} from "../../components/ui";

type Option = string | { value: string; label: string };
type Field = {
  key: string;
  label: string;
  kind: "currency" | "number" | "checkbox" | "days" | "multi" | "select" | "text";
  hint?: string;
  options?: Option[];
};
type Group = { pack_key: string; title: string; fields: Field[]; values: Record<string, unknown> };

const optionValue = (o: Option) => (typeof o === "string" ? o : o.value);
const optionLabel = (o: Option) => (typeof o === "string" ? o : o.label);

export function PracticeSettingsPage() {
  const groups = useQuery({
    queryKey: ["practice-settings"],
    queryFn: ({ signal }) => apiRequest<Group[]>("/setup/practice-settings", { signal }),
  });
  return (
    <div className="space-y-4">
      <PageHeader
        title="Practice Settings"
        subtitle="Rates, compliance thresholds, due dates and reminders for your profession."
        icon={<SettingsIcon size={22} className="text-brand-700" />}
      />
      {groups.isPending ? (
        <Spinner label="Loading" />
      ) : groups.isError ? (
        <Alert tone="error">{errorMessage(groups.error)}</Alert>
      ) : groups.data.length === 0 ? (
        <Alert tone="info">No profession pack with settings is installed in this workspace.</Alert>
      ) : (
        groups.data.map((g) => <GroupForm key={g.pack_key} group={g} />)
      )}
    </div>
  );
}

function initial(field: Field, value: unknown): unknown {
  if (field.kind === "days") return Array.isArray(value) ? value.join(", ") : "";
  if (field.kind === "multi") return Array.isArray(value) ? value : [];
  if (field.kind === "checkbox") return Boolean(value);
  return value ?? "";
}

function GroupForm({ group }: { group: Group }) {
  const { can } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const canEdit = can("customize_application");
  const [values, setValues] = useState<Record<string, unknown>>(() =>
    Object.fromEntries(group.fields.map((f) => [f.key, initial(f, group.values[f.key])])),
  );
  const set = (key: string, value: unknown) => setValues((v) => ({ ...v, [key]: value }));
  const save = useMutation({
    mutationFn: () =>
      apiRequest<Group>(`/setup/practice-settings/${group.pack_key}`, { method: "PUT", body: { values } }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["practice-settings"] });
      toast.show(`${group.title} settings saved.`);
    },
  });
  const err = save.error instanceof ApiError ? save.error : null;

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    save.mutate();
  }
  return (
    <form
      onSubmit={onSubmit}
      className="space-y-4 rounded-xl border border-slate-200/80 bg-white shadow-card p-5"
      noValidate
    >
      <h2 className="text-lg font-semibold text-slate-900">{group.title}</h2>
      {err && !Object.keys(err.fields).length && <Alert tone="error">{errorMessage(err)}</Alert>}
      <div className="grid gap-4 sm:grid-cols-2">
        {group.fields.map((f) => (
          <div key={f.key} className={f.kind === "multi" ? "sm:col-span-2" : undefined}>
            {f.kind === "checkbox" ? (
              <div>
                <Checkbox
                  label={f.label}
                  checked={Boolean(values[f.key])}
                  disabled={!canEdit}
                  onChange={(e) => set(f.key, e.target.checked)}
                />
                {f.hint && <p className="mt-1 text-xs text-slate-500">{f.hint}</p>}
              </div>
            ) : (
              <FormField
                label={f.label}
                hint={
                  f.kind === "days"
                    ? (f.hint ?? "Days before, separated by commas (e.g. 90, 30, 7).")
                    : f.hint
                }
                error={err?.fields[f.key]}
              >
                {({ id, describedBy, invalid }) =>
                  f.kind === "multi" ? (
                    <div
                      id={id}
                      aria-describedby={describedBy}
                      className="mt-1 flex flex-wrap gap-x-4 gap-y-1"
                    >
                      {(f.options ?? []).map((o) => {
                        const v = optionValue(o);
                        const chosen = (values[f.key] as string[]).includes(v);
                        return (
                          <Checkbox
                            key={v}
                            label={optionLabel(o)}
                            checked={chosen}
                            disabled={!canEdit}
                            onChange={(e) =>
                              set(
                                f.key,
                                e.target.checked
                                  ? [...(values[f.key] as string[]), v]
                                  : (values[f.key] as string[]).filter((x) => x !== v),
                              )
                            }
                          />
                        );
                      })}
                    </div>
                  ) : f.kind === "select" ? (
                    <select
                      id={id}
                      aria-describedby={describedBy}
                      className={controlClass(invalid)}
                      disabled={!canEdit}
                      value={String(values[f.key] ?? "")}
                      onChange={(e) => set(f.key, e.target.value)}
                    >
                      {(f.options ?? []).map((o) => (
                        <option key={optionValue(o)} value={optionValue(o)}>
                          {optionLabel(o)}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <Input
                      id={id}
                      aria-describedby={describedBy}
                      invalid={invalid}
                      disabled={!canEdit}
                      type={f.kind === "currency" || f.kind === "number" ? "number" : "text"}
                      step={f.kind === "currency" ? "0.01" : f.kind === "number" ? "any" : undefined}
                      inputMode={f.kind === "days" ? "numeric" : undefined}
                      value={String(values[f.key] ?? "")}
                      onChange={(e) => set(f.key, e.target.value)}
                    />
                  )
                }
              </FormField>
            )}
          </div>
        ))}
      </div>
      {canEdit && (
        <div>
          <Button type="submit" loading={save.isPending}>
            Save
          </Button>
        </div>
      )}
    </form>
  );
}

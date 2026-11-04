import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { errorMessage, fieldError } from "../../api/client";
import { usersApi } from "../../api/users";
import { Alert, Button, Card, PageHeader, SelectField, TextField, useToast } from "../../components/ui";
import { useAuth } from "../../auth/context";
import { nullIfBlank } from "../../lib/format";
import { registrationField } from "../../lib/registration";
import { useHierarchyRoles, useStaffProfiles } from "./useStaffRoles";

export function UserCreatePage() {
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();
  const profiles = useStaffProfiles();
  const roles = useHierarchyRoles();
  const { me } = useAuth();
  const registration = registrationField(me?.workspace_domain);
  const [form, setForm] = useState({
    email: "",
    name: "",
    profile: "",
    role: "",
    title: "",
    phone: "",
    mara: "",
  });
  const set = (key: keyof typeof form) => (value: string) => setForm((f) => ({ ...f, [key]: value }));

  const create = useMutation({
    mutationFn: () =>
      usersApi.create({
        email: form.email.trim(),
        name: form.name.trim(),
        profile_id: form.profile,
        role_id: form.role || null,
        title: nullIfBlank(form.title),
        phone: nullIfBlank(form.phone),
        mara_number: nullIfBlank(form.mara),
      }),
    onSuccess: (user) => {
      void queryClient.invalidateQueries({ queryKey: ["users"] });
      toast.show(`Invitation sent to ${user.email}.`);
      navigate(`/admin/users/${user.id}`);
    },
  });

  const knownFields = ["email", "name", "profile_id", "role_id", "title", "phone", "mara_number"];
  const unmappedError =
    create.isError && !knownFields.some((f) => fieldError(create.error, f))
      ? errorMessage(create.error)
      : null;

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    create.mutate();
  }

  return (
    <div>
      <PageHeader
        title="New user"
        subtitle="The user receives an e-mail invitation to set their password."
        breadcrumbs={[
          { label: "Home", to: "/" },
          { label: "Users", to: "/admin/users" },
          { label: "New user" },
        ]}
      />
      <Card>
        <form onSubmit={onSubmit} className="grid max-w-2xl gap-4 sm:grid-cols-2" noValidate>
          {unmappedError && (
            <div className="sm:col-span-2">
              <Alert tone="error">{unmappedError}</Alert>
            </div>
          )}
          <TextField
            label="Full name"
            required
            value={form.name}
            onChange={(e) => set("name")(e.target.value)}
            error={fieldError(create.error, "name")}
          />
          <TextField
            label="E-mail"
            type="email"
            required
            value={form.email}
            onChange={(e) => set("email")(e.target.value)}
            error={fieldError(create.error, "email")}
          />
          <SelectField
            label="Profile"
            required
            hint="What the user can do."
            value={form.profile}
            onChange={(e) => set("profile")(e.target.value)}
            error={fieldError(create.error, "profile_id")}
          >
            <option value="">Select a profile…</option>
            {profiles.data?.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </SelectField>
          <SelectField
            label="Role"
            hint="Where the user sits in the role hierarchy (whose records they see)."
            value={form.role}
            onChange={(e) => set("role")(e.target.value)}
            error={fieldError(create.error, "role_id")}
          >
            <option value="">No role</option>
            {roles.data?.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </SelectField>
          <TextField
            label="Job title"
            value={form.title}
            onChange={(e) => set("title")(e.target.value)}
            error={fieldError(create.error, "title")}
          />
          <TextField
            label="Phone"
            type="tel"
            value={form.phone}
            onChange={(e) => set("phone")(e.target.value)}
            error={fieldError(create.error, "phone")}
          />
          {registration && (
            <TextField
              label={registration.label}
              hint={registration.hint}
              inputMode={registration.digitsOnly ? "numeric" : "text"}
              maxLength={registration.maxLength}
              value={form.mara}
              onChange={(e) =>
                set("mara")(registration.digitsOnly ? e.target.value.replace(/\D/g, "") : e.target.value)
              }
              error={fieldError(create.error, "mara_number")}
            />
          )}
          <div className="flex gap-2 sm:col-span-2">
            <Button
              type="submit"
              loading={create.isPending}
              disabled={!form.name || !form.email || !form.profile}
            >
              Create and send invitation
            </Button>
            <Button variant="secondary" onClick={() => navigate("/admin/users")}>
              Cancel
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { errorMessage, fieldError } from "../../api/client";
import type { Role } from "../../api/types";
import { usersApi } from "../../api/users";
import { Alert, Button, Card, PageHeader, SelectField, TextField, useToast } from "../../components/ui";
import { nullIfBlank } from "../../lib/format";
import { useStaffRoles } from "./useStaffRoles";

export function UserCreatePage() {
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();
  const roles = useStaffRoles();
  const [form, setForm] = useState({
    email: "",
    name: "",
    role: "" as Role | "",
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
        role: form.role as Role,
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

  const knownFields = ["email", "name", "role", "title", "phone", "mara_number"];
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
            label="Role"
            required
            value={form.role}
            onChange={(e) => set("role")(e.target.value)}
            error={fieldError(create.error, "role")}
          >
            <option value="">Select a role…</option>
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
          <TextField
            label="MARA number"
            hint="7 digits; registered migration agents only."
            inputMode="numeric"
            maxLength={7}
            value={form.mara}
            onChange={(e) => set("mara")(e.target.value.replace(/\D/g, ""))}
            error={fieldError(create.error, "mara_number")}
          />
          <div className="flex gap-2 sm:col-span-2">
            <Button
              type="submit"
              loading={create.isPending}
              disabled={!form.name || !form.email || !form.role}
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

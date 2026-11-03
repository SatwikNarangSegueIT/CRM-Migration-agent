import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";
import { ApiError, errorMessage, fieldError } from "../../api/client";
import type { Role } from "../../api/types";
import { isLocked, usersApi, type User, type UserUpdateInput } from "../../api/users";
import { useAuth } from "../../auth/context";
import {
  Alert,
  Button,
  Card,
  ConfirmDialog,
  PageHeader,
  SelectField,
  Spinner,
  TextField,
  useToast,
} from "../../components/ui";
import { formatDateTime, nullIfBlank } from "../../lib/format";
import { NotFoundPage } from "../NotFoundPage";
import { UserStatusBadges } from "./UserStatusBadges";
import { useStaffRoles } from "./useStaffRoles";

type FormState = { name: string; role: Role; title: string; phone: string; mara: string };

function toForm(user: User): FormState {
  return {
    name: user.name,
    role: user.role,
    title: user.title ?? "",
    phone: user.phone ?? "",
    mara: user.mara_number ?? "",
  };
}

type ActionKey = "resend" | "resetMfa" | "unlock" | "revoke" | "deactivate" | "activate";

const ACTIONS: Record<ActionKey, { title: string; body: string; confirm: string; danger?: boolean }> = {
  resend: {
    title: "Resend invitation?",
    body: "A new invitation link is e-mailed. Earlier links stop working.",
    confirm: "Resend invitation",
  },
  resetMfa: {
    title: "Reset two-step verification?",
    body: "The user is signed out everywhere and must set up an authenticator app again at next sign-in.",
    confirm: "Reset MFA",
    danger: true,
  },
  unlock: {
    title: "Unlock account?",
    body: "The user can try to sign in again immediately.",
    confirm: "Unlock",
  },
  revoke: {
    title: "Sign out all sessions?",
    body: "The user is signed out on every device.",
    confirm: "Sign out everywhere",
    danger: true,
  },
  deactivate: {
    title: "Deactivate user?",
    body: "The user is signed out and can no longer sign in. History is kept.",
    confirm: "Deactivate",
    danger: true,
  },
  activate: { title: "Activate user?", body: "The user can sign in again.", confirm: "Activate" },
};

export function UserDetailPage() {
  const { id = "" } = useParams();
  const { me } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const roles = useStaffRoles();
  const user = useQuery({ queryKey: ["users", id], queryFn: ({ signal }) => usersApi.get(id, signal) });
  const [pending, setPending] = useState<ActionKey | null>(null);

  function onUserChanged(updated: User) {
    queryClient.setQueryData(["users", id], updated);
    void queryClient.invalidateQueries({ queryKey: ["users"], exact: false, refetchType: "none" });
  }

  const action = useMutation({
    mutationFn: async (key: ActionKey): Promise<string> => {
      const current = user.data!;
      switch (key) {
        case "resend":
          return (await usersApi.resendInvitation(id)).message;
        case "resetMfa":
          onUserChanged(await usersApi.resetMfa(id));
          return "Two-step verification reset.";
        case "unlock":
          onUserChanged(await usersApi.unlock(id));
          return "Account unlocked.";
        case "revoke":
          return (await usersApi.revokeSessions(id)).message;
        case "deactivate":
        case "activate":
          onUserChanged(
            await usersApi.update(id, { updated_at: current.updated_at, is_active: key === "activate" }),
          );
          return key === "activate" ? "User activated." : "User deactivated.";
      }
    },
    onSuccess: (message) => {
      setPending(null);
      toast.show(message);
    },
    onError: (error) => {
      setPending(null);
      toast.show(errorMessage(error), "error");
    },
  });

  if (user.isPending) return <Spinner label="Loading user" />;
  if (user.isError) {
    if (user.error instanceof ApiError && user.error.status === 404) return <NotFoundPage />;
    return <Alert tone="error">{errorMessage(user.error)}</Alert>;
  }
  const u = user.data;
  const isSelf = me?.user.id === u.id;
  const dialog = pending ? ACTIONS[pending] : null;

  return (
    <div>
      <PageHeader
        title={u.name}
        subtitle={
          <span className="flex flex-wrap items-center gap-2">
            <span>{u.email}</span>
            <UserStatusBadges user={u} />
          </span>
        }
        breadcrumbs={[{ label: "Home", to: "/" }, { label: "Users", to: "/admin/users" }, { label: u.name }]}
        actions={
          <>
            {!u.has_password && u.is_active && (
              <Button variant="secondary" onClick={() => setPending("resend")}>
                Resend invitation
              </Button>
            )}
            {isLocked(u) && (
              <Button variant="secondary" onClick={() => setPending("unlock")}>
                Unlock
              </Button>
            )}
            {u.mfa_enabled && (
              <Button variant="secondary" onClick={() => setPending("resetMfa")}>
                Reset MFA
              </Button>
            )}
            <Button variant="secondary" onClick={() => setPending("revoke")}>
              Sign out everywhere
            </Button>
            {u.is_active ? (
              <Button
                variant="danger"
                disabled={isSelf}
                title={isSelf ? "You cannot deactivate your own account" : undefined}
                onClick={() => setPending("deactivate")}
              >
                Deactivate
              </Button>
            ) : (
              <Button onClick={() => setPending("activate")}>Activate</Button>
            )}
          </>
        }
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card title="Details">
            <UserDetailsForm
              key={u.updated_at}
              user={u}
              isSelf={isSelf}
              roleOptions={roles.data ?? [{ value: u.role, label: u.role_label }]}
              onSaved={(updated) => {
                onUserChanged(updated);
                toast.show("User updated.");
              }}
              onReload={() => void user.refetch()}
            />
          </Card>
        </div>
        <Card title="Security">
          <dl className="space-y-3 text-sm">
            <div>
              <dt className="text-slate-500">Last sign-in</dt>
              <dd className="text-slate-900">{formatDateTime(u.last_login_at)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Two-step verification</dt>
              <dd className="text-slate-900">{u.mfa_enabled ? "Enabled" : "Not set up"}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Invitation</dt>
              <dd className="text-slate-900">{u.has_password ? "Accepted" : "Pending"}</dd>
            </div>
            {isLocked(u) && (
              <div>
                <dt className="text-slate-500">Locked until</dt>
                <dd className="text-red-700">{formatDateTime(u.locked_until)}</dd>
              </div>
            )}
            <div>
              <dt className="text-slate-500">Created</dt>
              <dd className="text-slate-900">{formatDateTime(u.created_at)}</dd>
            </div>
          </dl>
        </Card>
      </div>

      <ConfirmDialog
        open={dialog !== null}
        title={dialog?.title ?? ""}
        confirmLabel={dialog?.confirm}
        tone={dialog?.danger ? "danger" : "primary"}
        loading={action.isPending}
        onCancel={() => setPending(null)}
        onConfirm={() => pending && action.mutate(pending)}
      >
        {dialog?.body}
      </ConfirmDialog>
    </div>
  );
}

/** Edit form; keyed by `updated_at` so it re-initialises whenever the user record changes. */
function UserDetailsForm({
  user: u,
  isSelf,
  roleOptions,
  onSaved,
  onReload,
}: {
  user: User;
  isSelf: boolean;
  roleOptions: { value: Role; label: string }[];
  onSaved: (user: User) => void;
  onReload: () => void;
}) {
  const toast = useToast();
  const [form, setForm] = useState<FormState>(() => toForm(u));
  const save = useMutation({
    mutationFn: (body: UserUpdateInput) => usersApi.update(u.id, body),
    onSuccess: onSaved,
  });
  const conflict = save.error instanceof ApiError && save.error.status === 409;

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const body: UserUpdateInput = { updated_at: u.updated_at };
    if (form.name.trim() !== u.name) body.name = form.name.trim();
    if (form.role !== u.role) body.role = form.role;
    if (nullIfBlank(form.title) !== u.title) body.title = nullIfBlank(form.title);
    if (nullIfBlank(form.phone) !== u.phone) body.phone = nullIfBlank(form.phone);
    if (nullIfBlank(form.mara) !== u.mara_number) body.mara_number = nullIfBlank(form.mara);
    if (Object.keys(body).length === 1) {
      toast.show("No changes to save.", "info");
      return;
    }
    save.mutate(body);
  }

  const knownFields = ["name", "role", "title", "phone", "mara_number"];
  const generalError =
    save.isError && !conflict && !knownFields.some((f) => fieldError(save.error, f))
      ? errorMessage(save.error)
      : null;
  const set = (key: keyof FormState) => (value: string) => setForm((f) => ({ ...f, [key]: value }));

  return (
    <form onSubmit={onSubmit} className="grid gap-4 sm:grid-cols-2" noValidate>
      {conflict && (
        <div className="sm:col-span-2">
          <Alert tone="warning" title="This user was changed by someone else">
            <p>Reload to see the latest details, then make your changes again.</p>
            <Button
              size="sm"
              variant="secondary"
              className="mt-2"
              onClick={() => {
                save.reset();
                onReload();
              }}
            >
              Reload
            </Button>
          </Alert>
        </div>
      )}
      {generalError && (
        <div className="sm:col-span-2">
          <Alert tone="error">{generalError}</Alert>
        </div>
      )}
      <TextField
        label="Full name"
        required
        value={form.name}
        onChange={(e) => set("name")(e.target.value)}
        error={fieldError(save.error, "name")}
      />
      <SelectField
        label="Role"
        value={form.role}
        disabled={isSelf}
        hint={isSelf ? "You cannot change your own role." : undefined}
        onChange={(e) => set("role")(e.target.value)}
        error={fieldError(save.error, "role")}
      >
        {roleOptions.map((r) => (
          <option key={r.value} value={r.value}>
            {r.label}
          </option>
        ))}
      </SelectField>
      <TextField
        label="Job title"
        value={form.title}
        onChange={(e) => set("title")(e.target.value)}
        error={fieldError(save.error, "title")}
      />
      <TextField
        label="Phone"
        type="tel"
        value={form.phone}
        onChange={(e) => set("phone")(e.target.value)}
        error={fieldError(save.error, "phone")}
      />
      <TextField
        label="MARA number"
        hint="7 digits; registered migration agents only."
        inputMode="numeric"
        maxLength={7}
        value={form.mara}
        onChange={(e) => set("mara")(e.target.value.replace(/\D/g, ""))}
        error={fieldError(save.error, "mara_number")}
      />
      <div className="sm:col-span-2">
        <Button type="submit" loading={save.isPending} disabled={conflict}>
          Save changes
        </Button>
      </div>
    </form>
  );
}

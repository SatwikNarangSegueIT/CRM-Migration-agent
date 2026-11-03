import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { authApi } from "../api/auth";
import { errorMessage, fieldError } from "../api/client";
import { useAuth } from "../auth/context";
import { NewPasswordFields } from "../components/NewPasswordFields";
import { passwordsReady } from "../lib/password";
import { RecoveryCodes } from "../components/RecoveryCodes";
import { Alert, Badge, Button, Card, PageHeader, TextField, useToast } from "../components/ui";

function ChangePasswordCard() {
  const toast = useToast();
  const [current, setCurrent] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const change = useMutation({
    mutationFn: () => authApi.changePassword(current, password),
    onSuccess: (data) => {
      toast.show(data.message);
      setCurrent("");
      setPassword("");
      setConfirm("");
    },
  });
  const currentError = fieldError(change.error, "current_password");
  const newError = fieldError(change.error, "password") ?? fieldError(change.error, "new_password");

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    change.mutate();
  }

  return (
    <Card title="Change password">
      <form onSubmit={onSubmit} className="max-w-md space-y-4" noValidate>
        {change.isError && !currentError && !newError && (
          <Alert tone="error">{errorMessage(change.error)}</Alert>
        )}
        <TextField
          label="Current password"
          type="password"
          autoComplete="current-password"
          required
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          error={currentError}
        />
        <NewPasswordFields
          password={password}
          confirm={confirm}
          onPassword={setPassword}
          onConfirm={setConfirm}
          serverError={newError}
        />
        <p className="text-xs text-slate-500">Changing your password signs you out on other devices.</p>
        <Button
          type="submit"
          loading={change.isPending}
          disabled={!current || !passwordsReady(password, confirm)}
        >
          Update password
        </Button>
      </form>
    </Card>
  );
}

function TwoStepCard() {
  const { me, refresh } = useAuth();
  const [password, setPassword] = useState("");
  const [codes, setCodes] = useState<string[] | null>(null);
  const regenerate = useMutation({
    mutationFn: () => authApi.regenerateRecoveryCodes(password),
    onSuccess: (data) => {
      setCodes(data.recovery_codes);
      setPassword("");
    },
  });
  if (!me) return null;
  const remaining = me.session.recovery_codes_remaining;

  if (!me.user.mfa_enabled) {
    return (
      <Card title="Two-step verification" actions={<Badge tone="amber">Off</Badge>}>
        <p className="text-sm text-slate-600">Add an authenticator app to protect your account.</p>
        <Link
          to="/mfa/setup?next=/account"
          className="mt-3 inline-block rounded-md bg-brand-700 px-4 py-2 text-sm font-medium text-white hover:bg-brand-800"
        >
          Set up two-step verification
        </Link>
      </Card>
    );
  }

  return (
    <Card title="Two-step verification" actions={<Badge tone="green">On</Badge>}>
      {codes ? (
        <div className="max-w-md">
          <RecoveryCodes
            codes={codes}
            doneLabel="Done"
            onDone={() => {
              setCodes(null);
              void refresh();
            }}
          />
        </div>
      ) : (
        <form
          className="max-w-md space-y-4"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            regenerate.mutate();
          }}
        >
          <p className="text-sm text-slate-600">
            Recovery codes remaining: <strong>{remaining ?? "—"}</strong>
            {remaining !== null && remaining <= 3 && " — generate new codes soon."}
          </p>
          <p className="text-sm text-slate-600">
            Generating new codes replaces all existing ones. Lost your authenticator? Ask an administrator to
            reset two-step verification.
          </p>
          {regenerate.isError && !fieldError(regenerate.error, "password") && (
            <Alert tone="error">{errorMessage(regenerate.error)}</Alert>
          )}
          <TextField
            label="Confirm with your password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={fieldError(regenerate.error, "password")}
          />
          <Button type="submit" variant="secondary" loading={regenerate.isPending} disabled={!password}>
            Generate new recovery codes
          </Button>
        </form>
      )}
    </Card>
  );
}

export function AccountPage() {
  const { me } = useAuth();
  if (!me) return null;
  return (
    <div>
      <PageHeader
        title="Account settings"
        breadcrumbs={[{ label: "Home", to: me.user.is_staff ? "/" : "/portal" }, { label: "Account" }]}
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Profile">
          <dl className="grid grid-cols-3 gap-y-3 text-sm">
            <dt className="text-slate-500">Name</dt>
            <dd className="col-span-2 text-slate-900">{me.user.name}</dd>
            <dt className="text-slate-500">E-mail</dt>
            <dd className="col-span-2 break-all text-slate-900">{me.user.email}</dd>
            <dt className="text-slate-500">Profile</dt>
            <dd className="col-span-2 text-slate-900">{me.user.profile.name}</dd>
            {me.user.title && (
              <>
                <dt className="text-slate-500">Title</dt>
                <dd className="col-span-2 text-slate-900">{me.user.title}</dd>
              </>
            )}
            {me.user.mara_number && (
              <>
                <dt className="text-slate-500">MARA number</dt>
                <dd className="col-span-2 text-slate-900">{me.user.mara_number}</dd>
              </>
            )}
          </dl>
          <p className="mt-4 text-xs text-slate-500">
            Contact an administrator to change your profile details.
          </p>
        </Card>
        <TwoStepCard />
        <div className="lg:col-span-2">
          <ChangePasswordCard />
        </div>
      </div>
    </div>
  );
}

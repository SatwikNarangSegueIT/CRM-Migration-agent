import { TextField } from "./ui";

export const PASSWORD_HINT = "At least 12 characters. Avoid common passwords and your name or e-mail.";

/** New password + confirmation. Returns a client-side mismatch message via `mismatch`. */
export function NewPasswordFields({
  password,
  confirm,
  onPassword,
  onConfirm,
  serverError,
  label = "New password",
}: {
  password: string;
  confirm: string;
  onPassword: (v: string) => void;
  onConfirm: (v: string) => void;
  serverError?: string;
  label?: string;
}) {
  const mismatch = confirm.length > 0 && confirm !== password ? "Passwords do not match." : undefined;
  return (
    <>
      <TextField
        label={label}
        type="password"
        autoComplete="new-password"
        required
        hint={PASSWORD_HINT}
        value={password}
        onChange={(e) => onPassword(e.target.value)}
        error={serverError}
      />
      <TextField
        label="Confirm password"
        type="password"
        autoComplete="new-password"
        required
        value={confirm}
        onChange={(e) => onConfirm(e.target.value)}
        error={mismatch}
      />
    </>
  );
}

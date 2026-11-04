import { useId, useState } from "react";
import { passwordChecks, passwordStrength } from "../lib/password";
import { cx } from "./ui/cx";
import { FormField } from "./ui/FormField";
import { Input } from "./ui/Input";

const STRENGTH = [
  { label: "", bar: "bg-slate-200" },
  { label: "Weak", bar: "bg-red-500" },
  { label: "Fair", bar: "bg-amber-500" },
  { label: "Good", bar: "bg-emerald-500" },
  { label: "Strong", bar: "bg-emerald-600" },
];

/** Password input with a show/hide toggle. */
export function PasswordInput({
  id,
  describedBy,
  invalid,
  ...rest
}: React.InputHTMLAttributes<HTMLInputElement> & { describedBy?: string; invalid?: boolean }) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <Input
        id={id}
        aria-describedby={describedBy}
        invalid={invalid}
        type={visible ? "text" : "password"}
        className="pr-16"
        {...rest}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        className="absolute inset-y-0 right-0 px-3 text-xs font-medium text-slate-500 hover:text-slate-800 focus:outline-none focus-visible:text-brand-700"
        aria-pressed={visible}
      >
        {visible ? "Hide" : "Show"}
        <span className="sr-only"> password</span>
      </button>
    </div>
  );
}

/** New password + confirmation, with live requirement checks and a strength meter. */
export function NewPasswordFields({
  password,
  confirm,
  onPassword,
  onConfirm,
  serverError,
  label = "New password",
  email,
  name,
}: {
  password: string;
  confirm: string;
  onPassword: (v: string) => void;
  onConfirm: (v: string) => void;
  serverError?: string;
  label?: string;
  email?: string;
  name?: string;
}) {
  const checksId = useId();
  const mismatch = confirm.length > 0 && confirm !== password ? "Passwords don't match." : undefined;
  const checks = passwordChecks(password, { email, name });
  const strength = passwordStrength(password);
  const level = STRENGTH[strength]!;
  return (
    <>
      <FormField label={label} required error={serverError}>
        {({ id, describedBy, invalid }) => (
          <>
            <PasswordInput
              id={id}
              describedBy={[describedBy, checksId].filter(Boolean).join(" ")}
              invalid={invalid}
              autoComplete="new-password"
              required
              value={password}
              onChange={(e) => onPassword(e.target.value)}
            />
            <div className="mt-2 flex items-center gap-2" aria-hidden={!password}>
              <div className="flex flex-1 gap-1">
                {[1, 2, 3, 4].map((i) => (
                  <span
                    key={i}
                    className={cx(
                      "h-1 flex-1 rounded-full transition-colors",
                      i <= strength ? level.bar : "bg-slate-200",
                    )}
                  />
                ))}
              </div>
              <span className="w-12 text-right text-xs text-slate-500">{level.label}</span>
            </div>
            <ul id={checksId} className="mt-2 space-y-0.5" aria-live="polite">
              {checks.map((c) => (
                <li
                  key={c.key}
                  className={cx(
                    "flex items-center gap-1.5 text-xs",
                    c.ok ? "text-emerald-700" : "text-slate-500",
                  )}
                >
                  <span aria-hidden="true" className="inline-block w-3 text-center">
                    {c.ok ? "✓" : "•"}
                  </span>
                  {c.label}
                  <span className="sr-only">{c.ok ? " (met)" : " (not met)"}</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </FormField>
      <FormField label="Confirm password" required error={mismatch}>
        {({ id, describedBy, invalid }) => (
          <PasswordInput
            id={id}
            describedBy={describedBy}
            invalid={invalid}
            autoComplete="new-password"
            required
            value={confirm}
            onChange={(e) => onConfirm(e.target.value)}
          />
        )}
      </FormField>
    </>
  );
}

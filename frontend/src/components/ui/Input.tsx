import { forwardRef, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";
import { cx } from "./cx";
import { FormField } from "./FormField";

const CONTROL =
  "block w-full rounded-md border bg-white px-3 py-2 text-sm text-slate-900 shadow-sm placeholder:text-slate-400 " +
  "focus:outline-none focus:ring-2 focus:ring-brand-500 disabled:bg-slate-100 disabled:text-slate-500";

function controlClass(invalid: boolean, className?: string): string {
  return cx(CONTROL, invalid ? "border-red-400" : "border-slate-300", className);
}

export const Input = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }
>(function Input({ invalid = false, className, ...rest }, ref) {
  return (
    <input
      ref={ref}
      className={controlClass(invalid, className)}
      aria-invalid={invalid || undefined}
      {...rest}
    />
  );
});

export const Select = forwardRef<
  HTMLSelectElement,
  SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean }
>(function Select({ invalid = false, className, children, ...rest }, ref) {
  return (
    <select
      ref={ref}
      className={controlClass(invalid, className)}
      aria-invalid={invalid || undefined}
      {...rest}
    >
      {children}
    </select>
  );
});

type TextFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: ReactNode;
  error?: string;
};

export function TextField({ label, hint, error, required, ...rest }: TextFieldProps) {
  return (
    <FormField label={label} hint={hint} error={error} required={required}>
      {({ id, describedBy, invalid }) => (
        <Input id={id} aria-describedby={describedBy} invalid={invalid} required={required} {...rest} />
      )}
    </FormField>
  );
}

type SelectFieldProps = SelectHTMLAttributes<HTMLSelectElement> & {
  label: string;
  hint?: ReactNode;
  error?: string;
};

export function SelectField({ label, hint, error, required, children, ...rest }: SelectFieldProps) {
  return (
    <FormField label={label} hint={hint} error={error} required={required}>
      {({ id, describedBy, invalid }) => (
        <Select id={id} aria-describedby={describedBy} invalid={invalid} required={required} {...rest}>
          {children}
        </Select>
      )}
    </FormField>
  );
}

export function Checkbox({ label, ...rest }: InputHTMLAttributes<HTMLInputElement> & { label: ReactNode }) {
  return (
    <label className="flex items-start gap-2 text-sm text-slate-700">
      <input
        type="checkbox"
        className="mt-0.5 h-4 w-4 rounded border-slate-300 text-brand-700 focus:ring-brand-500"
        {...rest}
      />
      <span>{label}</span>
    </label>
  );
}

import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { InboxIcon } from "../icons";

/** Centred illustration-style empty state with an optional primary pill action. */
export function EmptyState({
  title,
  description,
  icon,
  action,
}: {
  title: string;
  description?: ReactNode;
  icon?: ReactNode;
  action?: { label: string; to?: string; onClick?: () => void };
}) {
  const pill =
    "mt-4 inline-flex items-center rounded-full bg-brand-700 px-5 py-2 text-sm font-medium text-white shadow-sm hover:bg-brand-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-700";
  return (
    <div className="flex flex-col items-center px-4 py-10 text-center">
      <span
        aria-hidden="true"
        className="flex h-20 w-20 items-center justify-center rounded-full bg-gradient-to-br from-brand-50 to-indigo-100 text-brand-600"
      >
        {icon ?? <InboxIcon size={36} />}
      </span>
      <p className="mt-4 text-base font-semibold text-slate-900">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-slate-600">{description}</p>}
      {action &&
        (action.to ? (
          <Link to={action.to} className={pill}>
            {action.label}
          </Link>
        ) : (
          <button type="button" onClick={action.onClick} className={pill}>
            {action.label}
          </button>
        ))}
    </div>
  );
}

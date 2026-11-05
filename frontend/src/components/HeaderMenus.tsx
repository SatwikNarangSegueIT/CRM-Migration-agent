import { useCallback, useRef, useState, type ReactNode } from "react";
import { useDismiss } from "../lib/useDismiss";
import { cx } from "./ui/cx";

/** Icon button with an accessible name and optional popover panel. */
export function HeaderIconButton({
  label,
  icon,
  onClick,
  children,
  badge,
}: {
  label: string;
  icon: ReactNode;
  onClick?: () => void;
  /** When provided, the button toggles a popover containing these children. */
  children?: ReactNode;
  badge?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useDismiss(open, ref, close);
  const hasPanel = children !== undefined;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-label={label}
        title={label}
        aria-haspopup={hasPanel ? "dialog" : undefined}
        aria-expanded={hasPanel ? open : undefined}
        onClick={() => (hasPanel ? setOpen((v) => !v) : onClick?.())}
        className="relative flex h-9 w-9 items-center justify-center rounded-full text-slate-500 hover:bg-slate-100 hover:text-slate-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-700"
      >
        {icon}
        {badge && (
          <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-red-500" aria-hidden="true" />
        )}
      </button>
      {hasPanel && open && (
        <div
          role="dialog"
          aria-label={label}
          className="absolute right-0 z-40 mt-2 w-72 rounded-xl border border-slate-200/80 bg-white text-sm shadow-pop"
        >
          {children}
        </div>
      )}
    </div>
  );
}

export function PanelHeader({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cx("border-b border-slate-100 px-4 py-3 font-semibold text-slate-900", className)}>
      {children}
    </div>
  );
}

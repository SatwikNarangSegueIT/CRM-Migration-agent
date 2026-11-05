import { useCallback, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/context";
import { initials } from "../lib/format";
import { useDismiss } from "../lib/useDismiss";

export function UserMenu({ accountPath = "/account" }: { accountPath?: string }) {
  const { me, signOut } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useDismiss(open, ref, close);

  if (!me) return null;

  async function handleSignOut() {
    setOpen(false);
    await signOut();
    navigate("/login", { replace: true });
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`User menu for ${me.user.name}`}
        onClick={() => setOpen((v) => !v)}
        className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-700 text-xs font-semibold text-white ring-offset-2 hover:ring-2 hover:ring-brand-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-700"
      >
        <span aria-hidden="true">{initials(me.user.name)}</span>
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 z-40 mt-2 w-64 rounded-xl border border-slate-200/80 bg-white py-1 text-sm shadow-pop"
        >
          <div className="flex items-center gap-3 border-b border-slate-100 px-4 py-3">
            <span
              aria-hidden="true"
              className="flex h-10 w-10 flex-none items-center justify-center rounded-full bg-brand-700 text-sm font-semibold text-white"
            >
              {initials(me.user.name)}
            </span>
            <div className="min-w-0">
              <p className="truncate font-semibold text-slate-900">{me.user.name}</p>
              <p className="truncate text-xs text-slate-500">{me.user.profile.name}</p>
              <p className="truncate text-xs text-slate-500">{me.user.email}</p>
            </div>
          </div>
          <Link
            role="menuitem"
            to={accountPath}
            onClick={close}
            className="block px-4 py-2 text-slate-700 hover:bg-slate-50"
          >
            Account settings
          </Link>
          <button
            role="menuitem"
            type="button"
            onClick={() => void handleSignOut()}
            className="block w-full px-4 py-2 text-left text-slate-700 hover:bg-slate-50"
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}

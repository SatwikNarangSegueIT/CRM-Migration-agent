import { useCallback, useRef, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import type { AppInfo, AppTab } from "../api/types";
import { useBranding } from "../lib/branding";
import { useDismiss } from "../lib/useDismiss";
import { appHref, rememberApp, tabHref } from "../navigation";
import {
  CalendarIcon,
  ChartIcon,
  CheckIcon,
  ChevronDownIcon,
  GaugeIcon,
  HomeIcon,
  InboxIcon,
  SettingsIcon,
} from "./icons";
import { iconFor, ObjectIcon } from "./record/ObjectIcon";
import { cx } from "./ui/cx";

type Icon = React.ComponentType<{ size?: number; className?: string }>;

/** A link in the sidebar that isn't one of the current app's tabs (Home, Contacts, Setup...). */
export type SideLink = { id: string; label: string; href: string; icon: Icon; active: boolean };

function tabIcon(tab: AppTab): Icon {
  switch (tab.kind) {
    case "home":
      return HomeIcon;
    case "object":
      return iconFor(tab.icon);
    case "calendar":
      return CalendarIcon;
    case "reports":
      return ChartIcon;
    case "dashboards":
      return GaugeIcon;
    case "queues":
      return InboxIcon;
  }
}

const itemClass = (active: boolean) =>
  cx(
    "group flex items-center gap-3 rounded-lg px-3 py-2 text-[13.5px] transition-colors",
    "focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand-600",
    active
      ? "bg-brand-50 font-semibold text-brand-800"
      : "font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900",
  );

const iconClass = (active: boolean) =>
  cx("flex-none", active ? "text-brand-700" : "text-slate-400 group-hover:text-slate-600");

function WorkspaceBadge() {
  const brand = useBranding();
  const initials =
    brand.name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((w) => w[0]?.toUpperCase())
      .join("") || "S";
  return (
    <Link
      to="/"
      aria-label={`${brand.name} home`}
      className="flex h-16 flex-none items-center gap-3 px-5 focus-visible:outline-none"
    >
      {brand.logoUrl ? (
        <img src={brand.logoUrl} alt="" className="h-8 w-8 flex-none rounded-lg object-contain" />
      ) : (
        <span
          aria-hidden="true"
          className="flex h-8 w-8 flex-none items-center justify-center rounded-lg bg-gradient-to-br from-brand-600 to-brand-900 text-xs font-bold tracking-wide text-white shadow-sm"
        >
          {initials}
        </span>
      )}
      <span className="min-w-0 truncate text-[15px] font-semibold tracking-tight text-slate-900">
        {brand.name}
      </span>
    </Link>
  );
}

/** Switches between the workspace's apps (e.g. Legal Practice and Analytics). */
function AppSwitcher({
  apps,
  current,
  onNavigate,
}: {
  apps: AppInfo[];
  current: AppInfo | undefined;
  onNavigate?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useDismiss(open, ref, close);
  if (!current) return null;
  if (apps.length < 2) {
    return (
      <div className="flex items-center gap-2.5 px-3 py-2">
        <ObjectIcon icon={current.icon} color={current.color} size={26} className="rounded-lg" />
        <span className="truncate text-sm font-semibold text-slate-900">{current.label}</span>
      </div>
    );
  }
  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`App: ${current.label}. Switch app`}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2.5 rounded-xl border border-slate-200/80 bg-white shadow-card px-3 py-2 text-left transition-colors hover:border-slate-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-600"
      >
        <ObjectIcon icon={current.icon} color={current.color} size={26} className="rounded-lg" />
        <span className="min-w-0 flex-1 truncate text-sm font-semibold text-slate-900">{current.label}</span>
        <ChevronDownIcon
          size={16}
          className={cx("text-slate-400 transition-transform", open && "rotate-180")}
        />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute inset-x-0 z-40 mt-1.5 rounded-xl border border-slate-200/80 bg-white p-1 shadow-pop"
        >
          {apps.map((a) => (
            <Link
              key={a.key}
              role="menuitem"
              to={appHref(a)}
              onClick={() => {
                rememberApp(a.key);
                close();
                onNavigate?.();
              }}
              className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm hover:bg-slate-50"
            >
              <ObjectIcon icon={a.icon} color={a.color} size={24} className="rounded-md" />
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium text-slate-900">{a.label}</span>
                {a.description && (
                  <span className="block truncate text-xs text-slate-500">{a.description}</span>
                )}
              </span>
              {a.key === current.key && <CheckIcon size={16} className="text-brand-700" />}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * The workspace's navigation: the app switcher, the current app's tabs as a vertical list (every tab is
 * visible at once, however many a profession has), then links outside the app (Setup).
 */
export function Sidebar({
  apps,
  app,
  activeTab,
  topLinks,
  bottomLinks,
  onPrefetch,
  onNavigate,
}: {
  apps: AppInfo[];
  app: AppInfo | undefined;
  activeTab: AppTab | undefined;
  topLinks: SideLink[];
  bottomLinks: SideLink[];
  onPrefetch: (t: AppTab) => void;
  onNavigate?: () => void;
}) {
  const plain = (l: SideLink) => {
    const Icon = l.icon;
    return (
      <li key={l.id}>
        <Link
          to={l.href}
          onClick={onNavigate}
          aria-current={l.active ? "page" : undefined}
          className={itemClass(l.active)}
        >
          <Icon size={18} className={iconClass(l.active)} />
          <span className="truncate">{l.label}</span>
        </Link>
      </li>
    );
  };
  return (
    <div className="flex h-full flex-col">
      <WorkspaceBadge />
      <nav aria-label="Apps" className="flex min-h-0 flex-1 flex-col">
        <div className="px-3 pb-2">
          <AppSwitcher apps={apps} current={app} onNavigate={onNavigate} />
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
          {topLinks.length > 0 && <ul className="mb-2 space-y-0.5">{topLinks.map(plain)}</ul>}
          {app && (
            <div role="navigation" aria-label={`${app.label} tabs`}>
              <ul className="space-y-0.5">
                {app.tabs.map((t) => {
                  const Icon = tabIcon(t);
                  const active = t === activeTab;
                  return (
                    <li key={tabHref(app, t)}>
                      <NavLink
                        to={tabHref(app, t)}
                        onClick={() => {
                          rememberApp(app.key);
                          onNavigate?.();
                        }}
                        onMouseEnter={() => onPrefetch(t)}
                        onFocus={() => onPrefetch(t)}
                        aria-current={active ? "page" : undefined}
                        className={itemClass(active)}
                      >
                        <Icon size={18} className={iconClass(active)} />
                        <span className="truncate">{t.label}</span>
                      </NavLink>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </div>
        {bottomLinks.length > 0 && (
          <ul className="space-y-0.5 border-t border-slate-200/80 px-3 py-3">{bottomLinks.map(plain)}</ul>
        )}
      </nav>
    </div>
  );
}

export const setupLink = (active: boolean): SideLink => ({
  id: "setup",
  label: "Setup",
  href: "/setup",
  icon: SettingsIcon,
  active,
});

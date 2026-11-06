import { useCallback, useRef, useState, type FocusEvent, type MouseEvent } from "react";
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
  ChevronLeftIcon,
  ChevronRightIcon,
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

const itemClass = (active: boolean, collapsed = false) =>
  cx(
    "group relative flex items-center rounded-lg py-2 text-[13.5px] transition-colors",
    collapsed ? "justify-center px-0" : "gap-3 px-3",
    "focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand-600",
    active
      ? "bg-brand-50 font-semibold text-brand-800 shadow-[inset_0_0_0_1px_rgb(var(--brand-100))]"
      : "font-medium text-slate-600 hover:bg-slate-100/80 hover:text-slate-900",
  );

/** Hover/focus label for an icon-only (collapsed) item: fixed-positioned so the scroll area can't clip it. */
type Hint = { label: string; top: number } | null;

const iconClass = (active: boolean) =>
  cx("flex-none", active ? "text-brand-700" : "text-slate-400 group-hover:text-slate-600");

function WorkspaceBadge({ collapsed }: { collapsed: boolean }) {
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
      className={cx(
        "flex h-16 flex-none items-center gap-3 focus-visible:outline-none",
        collapsed ? "justify-center px-0" : "px-5",
      )}
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
      {!collapsed && (
        <span className="min-w-0 truncate text-[15px] font-semibold tracking-tight text-slate-900">
          {brand.name}
        </span>
      )}
    </Link>
  );
}

/** Switches between the workspace's apps (e.g. Legal Practice and Analytics). */
function AppSwitcher({
  apps,
  current,
  collapsed,
  onNavigate,
}: {
  apps: AppInfo[];
  current: AppInfo | undefined;
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useDismiss(open, ref, close);
  if (!current) return null;
  if (apps.length < 2) {
    return (
      <div className={cx("flex items-center gap-2.5 py-2", collapsed ? "justify-center" : "px-3")}>
        <ObjectIcon icon={current.icon} color={current.color} size={26} className="rounded-lg" />
        {!collapsed && <span className="truncate text-sm font-semibold text-slate-900">{current.label}</span>}
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
        className={cx(
          "flex w-full items-center rounded-xl border border-slate-200/80 bg-white py-2 text-left shadow-card transition-colors hover:border-slate-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-600",
          collapsed ? "justify-center px-0" : "gap-2.5 px-3",
        )}
      >
        <ObjectIcon icon={current.icon} color={current.color} size={26} className="rounded-lg" />
        {!collapsed && (
          <>
            <span className="min-w-0 flex-1 truncate text-sm font-semibold text-slate-900">
              {current.label}
            </span>
            <ChevronDownIcon
              size={16}
              className={cx("text-slate-400 transition-transform", open && "rotate-180")}
            />
          </>
        )}
      </button>
      {open && (
        <div
          role="menu"
          className={cx(
            "absolute z-40 rounded-xl border border-slate-200/80 bg-white p-1 shadow-pop",
            collapsed ? "left-full top-0 ml-3 w-64" : "inset-x-0 mt-1.5",
          )}
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
  collapsed = false,
  onToggleCollapsed,
}: {
  apps: AppInfo[];
  app: AppInfo | undefined;
  activeTab: AppTab | undefined;
  topLinks: SideLink[];
  bottomLinks: SideLink[];
  onPrefetch: (t: AppTab) => void;
  onNavigate?: () => void;
  /** Icons only; each item's name shows beside it on hover or keyboard focus. */
  collapsed?: boolean;
  /** Shown as the collapse / expand button when given (not in the phone drawer). */
  onToggleCollapsed?: () => void;
}) {
  const [hint, setHint] = useState<Hint>(null);
  const showHint = (label: string) =>
    collapsed
      ? {
          onMouseEnter: (e: MouseEvent<HTMLElement>) => place(label, e.currentTarget),
          onMouseLeave: () => setHint(null),
          onFocus: (e: FocusEvent<HTMLElement>) => place(label, e.currentTarget),
          onBlur: () => setHint(null),
        }
      : {};
  const place = (label: string, el: HTMLElement) => {
    const r = el.getBoundingClientRect();
    setHint({ label, top: r.top + r.height / 2 });
  };
  const label = (text: string) =>
    collapsed ? <span className="sr-only">{text}</span> : <span className="truncate">{text}</span>;
  const plain = (l: SideLink) => {
    const Icon = l.icon;
    return (
      <li key={l.id}>
        <Link
          to={l.href}
          onClick={onNavigate}
          aria-current={l.active ? "page" : undefined}
          className={itemClass(l.active, collapsed)}
          {...showHint(l.label)}
        >
          <Icon size={18} className={iconClass(l.active)} />
          {label(l.label)}
        </Link>
      </li>
    );
  };
  return (
    <div className="flex h-full flex-col">
      <div className={cx("flex flex-none items-center", collapsed ? "flex-col" : "pr-3")}>
        <div className="min-w-0 flex-1">
          <WorkspaceBadge collapsed={collapsed} />
        </div>
        {onToggleCollapsed && (
          <button
            type="button"
            onClick={() => {
              setHint(null);
              onToggleCollapsed();
            }}
            aria-expanded={!collapsed}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-keyshortcuts="Control+B Meta+B"
            title={collapsed ? "Expand sidebar (Ctrl+B)" : "Collapse sidebar (Ctrl+B)"}
            className={cx(
              "flex-none rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700",
              "focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-600",
              collapsed && "-mt-2 mb-2",
            )}
          >
            {collapsed ? <ChevronRightIcon size={18} /> : <ChevronLeftIcon size={18} />}
          </button>
        )}
      </div>
      <nav aria-label="Apps" className="flex min-h-0 flex-1 flex-col">
        <div className={cx("pb-2", collapsed ? "px-2.5" : "px-3")}>
          <AppSwitcher apps={apps} current={app} collapsed={collapsed} onNavigate={onNavigate} />
        </div>
        <div className={cx("min-h-0 flex-1 overflow-y-auto pb-3", collapsed ? "px-2.5" : "px-3")}>
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
                        onMouseEnter={(e) => {
                          onPrefetch(t);
                          if (collapsed) place(t.label, e.currentTarget);
                        }}
                        onMouseLeave={() => setHint(null)}
                        onFocus={(e) => {
                          onPrefetch(t);
                          if (collapsed) place(t.label, e.currentTarget);
                        }}
                        onBlur={() => setHint(null)}
                        aria-current={active ? "page" : undefined}
                        className={itemClass(active, collapsed)}
                      >
                        <Icon size={18} className={iconClass(active)} />
                        {label(t.label)}
                      </NavLink>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </div>
        {bottomLinks.length > 0 && (
          <ul className={cx("space-y-0.5 border-t border-slate-200/70 py-3", collapsed ? "px-2.5" : "px-3")}>
            {bottomLinks.map(plain)}
          </ul>
        )}
      </nav>
      {collapsed && hint && (
        <div
          role="tooltip"
          className="pointer-events-none fixed left-[76px] z-50 -translate-y-1/2 whitespace-nowrap rounded-lg bg-slate-900 px-2.5 py-1.5 text-xs font-medium text-white shadow-pop"
          style={{ top: hint.top }}
        >
          {hint.label}
        </div>
      )}
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

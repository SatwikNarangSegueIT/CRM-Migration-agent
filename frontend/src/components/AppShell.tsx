import { useCallback, useState, type FormEvent } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/context";
import { activeApp, visibleApps, type VisibleApp } from "../navigation";
import { HeaderIconButton, PanelHeader } from "./HeaderMenus";
import {
  AppsIcon,
  BellIcon,
  CloseIcon,
  HelpIcon,
  InboxIcon,
  MenuIcon,
  SearchIcon,
  SettingsIcon,
} from "./icons";
import { Logo } from "./Logo";
import { useToast } from "./ui";
import { cx } from "./ui/cx";
import { UserMenu } from "./UserMenu";

function RailItem({
  app,
  active,
  onNavigate,
}: {
  app: VisibleApp;
  active: boolean;
  onNavigate?: () => void;
}) {
  const Icon = app.icon;
  return (
    <li>
      <Link
        to={app.href}
        onClick={onNavigate}
        aria-current={active ? "page" : undefined}
        className={cx(
          "mx-1.5 flex flex-col items-center gap-1 rounded-lg border px-1 py-2 text-center text-[11px] font-medium leading-tight",
          "focus-visible:outline focus-visible:outline-2 focus-visible:outline-white",
          active
            ? "border-white/70 bg-white/10 text-white"
            : "border-transparent text-blue-100 hover:bg-white/10 hover:text-white",
        )}
      >
        <Icon size={22} />
        <span className="w-full truncate" title={app.label}>
          {app.railLabel ?? app.label}
        </span>
      </Link>
    </li>
  );
}

function AppRail({
  apps,
  current,
  onNavigate,
}: {
  apps: VisibleApp[];
  current?: VisibleApp;
  onNavigate?: () => void;
}) {
  return (
    <nav aria-label="Apps" className="h-full">
      <ul className="flex flex-col gap-1 py-3">
        {apps.map((app) => (
          <RailItem key={app.id} app={app} active={app.id === current?.id} onNavigate={onNavigate} />
        ))}
      </ul>
    </nav>
  );
}

function GlobalSearch() {
  const toast = useToast();
  const [value, setValue] = useState("");
  function onSubmit(event: FormEvent) {
    event.preventDefault();
    toast.show("Global search arrives with the CRM records in the next phase.", "info");
  }
  return (
    <form role="search" onSubmit={onSubmit} className="mx-auto w-full max-w-xl">
      <label htmlFor="global-search" className="sr-only">
        Search
      </label>
      <div className="relative">
        <SearchIcon
          size={18}
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
        />
        <input
          id="global-search"
          type="search"
          placeholder="Search..."
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="h-9 w-full rounded-full border border-slate-300 bg-slate-50 pl-10 pr-4 text-sm placeholder:text-slate-500 focus:border-brand-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-200"
        />
      </div>
    </form>
  );
}

export function AppShell() {
  const { can } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const closeDrawer = useCallback(() => setDrawerOpen(false), []);
  const apps = visibleApps(can);
  const current = activeApp(apps, pathname);

  return (
    <div className="flex min-h-screen bg-slate-100">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2"
      >
        Skip to content
      </a>

      {/* Left icon rail (desktop) */}
      <aside className="sticky top-0 hidden h-screen w-[72px] flex-none bg-[#032d60] md:block">
        <div className="flex h-14 items-center justify-center border-b border-white/10 text-white">
          <AppsIcon size={22} />
        </div>
        <AppRail apps={apps} current={current} />
      </aside>

      {/* Mobile drawer */}
      {drawerOpen && (
        <div className="fixed inset-0 z-50 md:hidden" role="dialog" aria-modal="true" aria-label="Apps">
          <div className="absolute inset-0 bg-slate-900/40" onClick={closeDrawer} aria-hidden="true" />
          <div className="absolute inset-x-0 top-0 bg-[#032d60] pb-2 shadow-xl">
            <div className="flex h-14 items-center justify-between px-4 text-white">
              <span className="font-semibold">Apps</span>
              <button
                type="button"
                aria-label="Close apps menu"
                onClick={closeDrawer}
                className="rounded p-1 hover:bg-white/10"
              >
                <CloseIcon />
              </button>
            </div>
            <nav aria-label="Apps (mobile)">
              <ul className="grid grid-cols-4 gap-1 px-2">
                {apps.map((app) => (
                  <RailItem key={app.id} app={app} active={app.id === current?.id} onNavigate={closeDrawer} />
                ))}
              </ul>
            </nav>
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Global header */}
        <header className="sticky top-0 z-30 border-b border-slate-200 bg-white">
          <div className="flex h-14 items-center gap-3 px-3 sm:px-4">
            <button
              type="button"
              aria-label="Open apps menu"
              onClick={() => setDrawerOpen(true)}
              className="rounded p-1.5 text-slate-600 hover:bg-slate-100 md:hidden"
            >
              <MenuIcon />
            </button>
            <Link to="/" className="flex-none" aria-label="MigrateCRM home">
              <Logo />
            </Link>
            <div className="hidden flex-1 sm:block">
              <GlobalSearch />
            </div>
            <div className="ml-auto flex items-center gap-1">
              <HeaderIconButton
                label="Help"
                icon={<HelpIcon />}
                onClick={() =>
                  toast.show("Help centre coming soon. Contact your administrator for assistance.", "info")
                }
              />
              {can("user.manage") && (
                <HeaderIconButton
                  label="Settings"
                  icon={<SettingsIcon />}
                  onClick={() => navigate("/admin/users")}
                />
              )}
              <HeaderIconButton label="Notifications" icon={<BellIcon />}>
                <PanelHeader>Notifications</PanelHeader>
                <div className="flex flex-col items-center px-4 py-6 text-center text-slate-500">
                  <InboxIcon size={28} />
                  <p className="mt-2">You're all caught up.</p>
                </div>
              </HeaderIconButton>
              <div className="ml-1">
                <UserMenu />
              </div>
            </div>
          </div>
          <div className="px-3 pb-2 sm:hidden">
            <GlobalSearch />
          </div>

          {/* App bar: app name + tabs */}
          {current && (
            <div className="flex items-end gap-6 overflow-x-auto border-t border-slate-200 px-4">
              <p className="flex-none py-2.5 text-lg font-semibold text-slate-900">{current.label}</p>
              {current.visibleTabs.length > 0 && (
                <nav aria-label={`${current.label} tabs`} className="flex gap-1">
                  {current.visibleTabs.map((tab) => (
                    <NavLink
                      key={tab.to}
                      to={tab.to}
                      end={tab.end}
                      className={({ isActive }) =>
                        cx(
                          "whitespace-nowrap border-b-[3px] px-3 py-3 text-sm",
                          isActive
                            ? "border-brand-700 font-semibold text-slate-900"
                            : "border-transparent text-slate-600 hover:border-slate-300 hover:text-slate-900",
                        )
                      }
                    >
                      {tab.label}
                    </NavLink>
                  ))}
                </nav>
              )}
            </div>
          )}
        </header>

        <main id="main" className="w-full flex-1 px-3 py-4 sm:px-4">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

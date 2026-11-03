import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { workspaceApi } from "../api/records";
import type { AppInfo } from "../api/types";
import { useAuth } from "../auth/context";
import { recordPath, useApps } from "../lib/records";
import { useDismiss } from "../lib/useDismiss";
import { activeTab, appHref, currentApp, rememberApp, tabHref } from "../navigation";
import { HeaderIconButton, PanelHeader } from "./HeaderMenus";
import {
  AppsIcon,
  BellIcon,
  BuildingIcon,
  CloseIcon,
  HelpIcon,
  HomeIcon,
  InboxIcon,
  MenuIcon,
  PersonIcon,
  SearchIcon,
  SettingsIcon,
} from "./icons";
import { Logo } from "./Logo";
import { iconFor, ObjectIcon } from "./record/ObjectIcon";
import { cx } from "./ui/cx";
import { UserMenu } from "./UserMenu";

type RailEntry = {
  id: string;
  label: string;
  href: string;
  icon: React.ComponentType<{ size?: number }>;
  active: boolean;
  app?: AppInfo;
};

function RailItem({ entry, onNavigate }: { entry: RailEntry; onNavigate?: () => void }) {
  const Icon = entry.icon;
  return (
    <li>
      <Link
        to={entry.href}
        onClick={() => {
          if (entry.app) rememberApp(entry.app.key);
          onNavigate?.();
        }}
        aria-current={entry.active ? "page" : undefined}
        className={cx(
          "mx-1.5 flex flex-col items-center gap-1 rounded-lg border px-1 py-2 text-center text-[11px] font-medium leading-tight",
          "focus-visible:outline focus-visible:outline-2 focus-visible:outline-white",
          entry.active
            ? "border-white/70 bg-white/10 text-white"
            : "border-transparent text-blue-100 hover:bg-white/10 hover:text-white",
        )}
      >
        <Icon size={22} />
        <span className="w-full truncate" title={entry.label}>
          {entry.label}
        </span>
      </Link>
    </li>
  );
}

function GlobalSearch() {
  const navigate = useNavigate();
  const [value, setValue] = useState("");
  const [open, setOpen] = useState(false);
  const [debounced, setDebounced] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useDismiss(open, ref, close);
  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(value.trim()), 250);
    return () => window.clearTimeout(t);
  }, [value]);
  const results = useQuery({
    queryKey: ["search", "typeahead", debounced],
    queryFn: ({ signal }) => workspaceApi.search(debounced, signal, 3),
    enabled: open && debounced.length >= 2,
    staleTime: 10_000,
  });
  const recent = useQuery({
    queryKey: ["recent"],
    queryFn: ({ signal }) => workspaceApi.recent(signal, 6),
    enabled: open && debounced.length < 2,
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!value.trim()) return;
    setOpen(false);
    navigate(`/search?q=${encodeURIComponent(value.trim())}`);
  }
  return (
    <div ref={ref} className="relative mx-auto w-full max-w-xl">
      <form role="search" onSubmit={onSubmit}>
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
            autoComplete="off"
            placeholder="Search..."
            value={value}
            onFocus={() => setOpen(true)}
            onChange={(e) => {
              setValue(e.target.value);
              setOpen(true);
            }}
            className="h-9 w-full rounded-full border border-slate-300 bg-slate-50 pl-10 pr-4 text-sm placeholder:text-slate-500 focus:border-brand-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-200"
          />
        </div>
      </form>
      {open && (
        <div className="absolute left-0 right-0 z-40 mt-1 max-h-[70vh] overflow-y-auto rounded-lg border border-slate-200 bg-white py-1 text-sm shadow-xl">
          {debounced.length < 2 ? (
            <>
              <p className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                Recent items
              </p>
              {recent.data?.length === 0 && (
                <p className="px-3 py-2 text-slate-500">Records you view appear here.</p>
              )}
              {recent.data?.map((r) => (
                <Link
                  key={r.id}
                  to={recordPath(r.object, r.id)}
                  onClick={close}
                  className="flex items-center gap-2 px-3 py-2 hover:bg-slate-50"
                >
                  <ObjectIcon icon={r.icon} color={r.color} size={22} />
                  <span className="truncate">{r.name}</span>
                  <span className="ml-auto text-xs text-slate-500">{r.object_label}</span>
                </Link>
              ))}
            </>
          ) : results.isFetching && !results.data ? (
            <p className="px-3 py-2 text-slate-500">Searching…</p>
          ) : (
            <>
              {results.data?.groups.flatMap((g) =>
                g.items.map((r) => (
                  <Link
                    key={r.id}
                    to={recordPath(g.object, r.id)}
                    onClick={close}
                    className="flex items-center gap-2 px-3 py-2 hover:bg-slate-50"
                  >
                    <ObjectIcon icon={g.icon} color={g.color} size={22} />
                    <span className="truncate">{r.name}</span>
                    <span className="ml-auto text-xs text-slate-500">{g.label}</span>
                  </Link>
                )),
              )}
              {results.data?.groups.length === 0 && <p className="px-3 py-2 text-slate-500">No matches.</p>}
              <button
                type="button"
                className="block w-full border-t border-slate-100 px-3 py-2 text-left text-brand-700 hover:bg-slate-50"
                onClick={() => {
                  close();
                  navigate(`/search?q=${encodeURIComponent(value.trim())}`);
                }}
              >
                Show all results for "{value.trim()}"
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function Notifications() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const data = useQuery({
    queryKey: ["notifications"],
    queryFn: ({ signal }) => workspaceApi.notifications(signal),
    refetchInterval: 60_000,
  });
  const readAll = useMutation({
    mutationFn: workspaceApi.readAll,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });
  const unread = data.data?.unread ?? 0;
  return (
    <HeaderIconButton
      label={unread ? `Notifications (${unread} unread)` : "Notifications"}
      icon={<BellIcon />}
      badge={unread > 0}
    >
      <PanelHeader className="flex items-center justify-between">
        <span>Notifications</span>
        {unread > 0 && (
          <button
            type="button"
            className="text-xs font-normal text-brand-700 hover:underline"
            onClick={() => readAll.mutate()}
          >
            Mark all as read
          </button>
        )}
      </PanelHeader>
      {!data.data || data.data.items.length === 0 ? (
        <div className="flex flex-col items-center px-4 py-6 text-center text-slate-500">
          <InboxIcon size={28} />
          <p className="mt-2">You're all caught up.</p>
        </div>
      ) : (
        <ul className="max-h-96 divide-y divide-slate-100 overflow-y-auto">
          {data.data.items.map((n) => (
            <li key={n.id}>
              <button
                type="button"
                className={cx(
                  "block w-full px-4 py-2.5 text-left hover:bg-slate-50",
                  !n.read && "bg-brand-50/50",
                )}
                onClick={() => {
                  void workspaceApi
                    .readNotification(n.id)
                    .then(() => queryClient.invalidateQueries({ queryKey: ["notifications"] }));
                  if (n.link) navigate(n.link);
                }}
              >
                <p className={cx("text-sm", !n.read && "font-semibold")}>{n.title}</p>
                {n.body && <p className="text-xs text-slate-600">{n.body}</p>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </HeaderIconButton>
  );
}

export function AppShell() {
  const { canSeeSetup, object } = useAuth();
  const navigate = useNavigate();
  const { pathname, search } = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const closeDrawer = useCallback(() => setDrawerOpen(false), []);
  const apps = useApps();
  const list = apps.data ?? [];
  const inSetup = pathname.startsWith("/setup") || pathname.startsWith("/admin");
  const app = inSetup ? undefined : currentApp(list, pathname, search);
  const tab = app ? activeTab(app, pathname, search) : undefined;

  useEffect(() => {
    if (app) rememberApp(app.key);
  }, [app]);

  const entries: RailEntry[] = [
    { id: "home", label: "Home", href: "/", icon: HomeIcon, active: pathname === "/" },
    ...(object("contact").read
      ? [
          {
            id: "contacts",
            label: "Contacts",
            href: "/o/contact",
            icon: PersonIcon,
            active: !app && pathname.startsWith("/o/contact"),
          },
        ]
      : []),
    ...(object("account").read
      ? [
          {
            id: "accounts",
            label: "Accounts",
            href: "/o/account",
            icon: BuildingIcon,
            active: !app && pathname.startsWith("/o/account"),
          },
        ]
      : []),
    ...list.map((a) => ({
      id: a.key,
      label: a.label,
      href: appHref(a),
      icon: iconFor(a.icon),
      active: a.key === app?.key,
      app: a,
    })),
    ...(canSeeSetup
      ? [{ id: "setup", label: "Setup", href: "/setup", icon: SettingsIcon, active: inSetup }]
      : []),
  ];

  return (
    <div className="flex min-h-screen bg-slate-100">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2"
      >
        Skip to content
      </a>

      <aside className="sticky top-0 hidden h-screen w-[76px] flex-none overflow-y-auto bg-[#032d60] md:block">
        <div className="flex h-14 items-center justify-center border-b border-white/10 text-white">
          <AppsIcon size={22} />
        </div>
        <nav aria-label="Apps">
          <ul className="flex flex-col gap-1 py-3">
            {entries.map((e) => (
              <RailItem key={e.id} entry={e} />
            ))}
          </ul>
        </nav>
      </aside>

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
                {entries.map((e) => (
                  <RailItem key={e.id} entry={e} onNavigate={closeDrawer} />
                ))}
              </ul>
            </nav>
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
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
            <Link to="/" className="flex-none" aria-label="Home">
              <Logo />
            </Link>
            <div className="hidden flex-1 sm:block">
              <GlobalSearch />
            </div>
            <div className="ml-auto flex items-center gap-1">
              <HeaderIconButton label="Help" icon={<HelpIcon />}>
                <PanelHeader>Help</PanelHeader>
                <ul className="space-y-2 px-4 py-3 text-slate-700">
                  <li>Use the search bar to find any record you can access.</li>
                  <li>Pin a list view to make it your default.</li>
                  <li>Ask your administrator to adjust fields, layouts or access in Setup.</li>
                </ul>
              </HeaderIconButton>
              {canSeeSetup && (
                <HeaderIconButton label="Setup" icon={<SettingsIcon />} onClick={() => navigate("/setup")} />
              )}
              <Notifications />
              <div className="ml-1">
                <UserMenu />
              </div>
            </div>
          </div>
          <div className="px-3 pb-2 sm:hidden">
            <GlobalSearch />
          </div>

          {app && (
            <div className="flex items-end gap-6 overflow-x-auto border-t border-slate-200 px-4">
              <p className="flex flex-none items-center gap-2 py-2.5 text-lg font-semibold text-slate-900">
                <ObjectIcon icon={app.icon} color={app.color} size={24} />
                {app.label}
              </p>
              <nav aria-label={`${app.label} tabs`} className="flex gap-1">
                {app.tabs.map((t) => {
                  const href = tabHref(app, t);
                  const isActive = t === tab;
                  return (
                    <NavLink
                      key={href}
                      to={href}
                      onClick={() => rememberApp(app.key)}
                      aria-current={isActive ? "page" : undefined}
                      className={cx(
                        "whitespace-nowrap border-b-[3px] px-3 py-3 text-sm",
                        isActive
                          ? "border-brand-700 font-semibold text-slate-900"
                          : "border-transparent text-slate-600 hover:border-slate-300 hover:text-slate-900",
                      )}
                    >
                      {t.label}
                    </NavLink>
                  );
                })}
              </nav>
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

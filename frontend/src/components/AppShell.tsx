import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { metaApi, recordsApi, workspaceApi } from "../api/records";
import type { AppInfo, AppTab } from "../api/types";
import { useAuth } from "../auth/context";
import { recordPath, useApps } from "../lib/records";
import { useDismiss } from "../lib/useDismiss";
import { activeTab, appHref, currentApp, rememberApp } from "../navigation";
import { AppTabs } from "./AppTabs";
import { HeaderIconButton, PanelHeader } from "./HeaderMenus";
import {
  BellIcon,
  BuildingIcon,
  CloseIcon,
  HomeIcon,
  InboxIcon,
  MenuIcon,
  PersonIcon,
  SearchIcon,
  SettingsIcon,
} from "./icons";
import { useBranding } from "../lib/branding";
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
          "relative mx-2 flex flex-col items-center gap-1 rounded-lg px-1 py-2 text-center text-[11px] font-medium leading-tight transition-colors",
          "focus-visible:outline focus-visible:outline-2 focus-visible:outline-white",
          entry.active ? "bg-white/10 text-white" : "text-slate-400 hover:bg-white/5 hover:text-white",
        )}
      >
        {entry.active && (
          <span
            aria-hidden="true"
            className="absolute -left-2 top-2 bottom-2 w-1 rounded-r-full bg-brand-400"
          />
        )}
        <Icon size={20} />
        <span
          className={cx("w-full truncate", entry.label.length > 9 && "text-[10px] tracking-tight")}
          title={entry.label}
        >
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
  const brand = useBranding();
  const { pathname, search } = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const closeDrawer = useCallback(() => setDrawerOpen(false), []);
  const apps = useApps();
  const list = apps.data ?? [];
  const inSetup = pathname.startsWith("/setup") || pathname.startsWith("/admin");
  const app = inSetup ? undefined : currentApp(list, pathname, search);
  const tab = app ? activeTab(app, pathname, search) : undefined;
  const queryClient = useQueryClient();
  // Start loading a tab's layout while the pointer is on it, so the click shows the page at once.
  const prefetchTab = (t: AppTab) => {
    if (t.kind !== "object" || !t.object) return;
    const api = t.object;
    void queryClient.prefetchQuery({
      queryKey: ["meta", "object", api],
      queryFn: ({ signal }) => metaApi.object(api, signal),
      staleTime: 5 * 60_000,
    });
    void queryClient.prefetchQuery({
      queryKey: ["list-views", api],
      queryFn: ({ signal }) => recordsApi.listViews(api, signal),
    });
  };

  useEffect(() => {
    if (app) rememberApp(app.key);
  }, [app]);

  // Object names follow the workspace's terminology (e.g. "Clients" for a law firm); app tabs carry them.
  const objectLabel = (api: string, fallback: string) =>
    list.flatMap((a) => a.tabs).find((t) => t.kind === "object" && t.object === api)?.label ?? fallback;
  // A domain workspace's own app is its home page, and its tabs already hold clients and organisations:
  // the rail then lists only the apps, so nothing appears twice.
  const domainWorkspace = list.some((a) => a.is_primary);
  const generic: RailEntry[] = domainWorkspace
    ? []
    : [
        { id: "home", label: "Home", href: "/", icon: HomeIcon, active: pathname === "/" },
        ...(object("contact").read
          ? [
              {
                id: "contacts",
                label: objectLabel("contact", "Contacts"),
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
                label: objectLabel("account", "Accounts"),
                href: "/o/account",
                icon: BuildingIcon,
                active: !app && pathname.startsWith("/o/account"),
              },
            ]
          : []),
      ];
  const entries: RailEntry[] = [
    ...generic,
    ...list.map((a) => ({
      id: a.key,
      label: domainWorkspace ? a.label.split(" ")[0]! : a.label,
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
    <div className="flex min-h-screen bg-slate-50">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2"
      >
        Skip to content
      </a>

      <aside className="sticky top-0 hidden h-screen w-[76px] flex-none overflow-y-auto bg-slate-900 md:block">
        <Link
          to="/"
          aria-label="Home"
          className="flex h-14 items-center justify-center border-b border-white/5"
        >
          <img src={brand.logoUrl ?? "/favicon.svg"} alt="" className="h-8 w-8 rounded-lg" />
        </Link>
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
          <div className="absolute inset-x-0 top-0 bg-slate-900 pb-2 shadow-xl">
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
            <Link to="/" className="flex-none md:hidden" aria-label="Home">
              <Logo />
            </Link>
            <div className="hidden flex-1 sm:block">
              <GlobalSearch />
            </div>
            <div className="ml-auto flex items-center gap-1">
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
            <div className="flex items-end gap-6 border-t border-slate-200 px-4">
              <p className="flex flex-none items-center gap-2 py-2.5 text-lg font-semibold text-slate-900">
                <ObjectIcon icon={app.icon} color={app.color} size={24} />
                {app.label}
              </p>
              <AppTabs app={app} active={tab} onPrefetch={prefetchTab} />
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

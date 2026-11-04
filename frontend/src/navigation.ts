// App navigation derived from /meta/apps (configurable in Setup -> Apps).
import type { AppInfo, AppTab } from "./api/types";

const LAST_APP_KEY = "crm.lastApp";

export function tabHref(app: AppInfo, tab: AppTab): string {
  switch (tab.kind) {
    case "home":
      return `/app/${app.key}`;
    case "object":
      return `/o/${tab.object}`;
    case "calendar":
      return "/calendar";
    case "reports":
      return "/reports";
    case "dashboards":
      return "/dashboards";
    case "queues":
      return "/o/case?scope=queue";
  }
}

export function appHref(app: AppInfo): string {
  const first = app.tabs[0];
  return first ? tabHref(app, first) : `/app/${app.key}`;
}

export function rememberApp(key: string): void {
  try {
    sessionStorage.setItem(LAST_APP_KEY, key);
  } catch {
    // Private mode: navigation still works, the app just isn't remembered.
  }
}

function lastApp(): string | null {
  try {
    return sessionStorage.getItem(LAST_APP_KEY);
  } catch {
    return null;
  }
}

function tabMatches(app: AppInfo, tab: AppTab, pathname: string, search: string): boolean {
  const href = tabHref(app, tab);
  const [path, query] = href.split("?");
  if (query) return pathname === path && search.includes(query);
  if (tab.kind === "home") return pathname === path;
  return pathname === path || pathname.startsWith(`${path}/`);
}

/** The app whose tabs to show: the one in the URL, the last used one if it contains this page, or any app that does. */
export function currentApp(apps: AppInfo[], pathname: string, search: string): AppInfo | undefined {
  const m = /^\/app\/([^/]+)/.exec(pathname);
  if (m) return apps.find((a) => a.key === m[1]);
  if (pathname === "/") return apps.find((a) => a.is_primary);
  const contains = (a: AppInfo) => a.tabs.some((t) => tabMatches(a, t, pathname, search));
  const remembered = apps.find((a) => a.key === lastApp());
  if (remembered && contains(remembered)) return remembered;
  return apps.find(contains);
}

export function activeTab(app: AppInfo, pathname: string, search: string): AppTab | undefined {
  // Prefer the most specific match (e.g. "Queues" over "Cases").
  const matches = app.tabs.filter((t) => tabMatches(app, t, pathname, search));
  return matches.find((t) => tabHref(app, t).includes("?")) ?? matches[0];
}

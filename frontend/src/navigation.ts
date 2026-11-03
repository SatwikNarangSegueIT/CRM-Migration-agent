// Data-driven app navigation for the left rail and the app bar tabs.
// Add a new app (Contacts, Accounts, Sales, Service…) by appending to APPS.
import type { ComponentType, SVGProps } from "react";
import { HomeIcon, ShieldIcon } from "./components/icons";

export type AppTab = { to: string; label: string; permission?: string; end?: boolean };

export type AppDef = {
  id: string;
  label: string;
  /** Short label for the narrow rail (defaults to `label`). */
  railLabel?: string;
  icon: ComponentType<SVGProps<SVGSVGElement> & { size?: number }>;
  /** Where the rail item links to when no tab is available. */
  to: string;
  /** Path prefixes that belong to this app (used to highlight the active app). */
  match: (pathname: string) => boolean;
  tabs: AppTab[];
  /** Shown only if the user holds this permission; apps with tabs need at least one visible tab. */
  permission?: string;
};

export const APPS: AppDef[] = [
  {
    id: "home",
    label: "Home",
    icon: HomeIcon,
    to: "/",
    match: (p) => p === "/" || p.startsWith("/account") || p === "/forbidden",
    tabs: [],
  },
  {
    id: "admin",
    label: "Administration",
    railLabel: "Admin",
    icon: ShieldIcon,
    to: "/admin/users",
    match: (p) => p.startsWith("/admin"),
    tabs: [
      { to: "/admin/users", label: "Users", permission: "user.manage" },
      { to: "/admin/audit", label: "Audit Log", permission: "audit.read" },
    ],
  },
];

export type VisibleApp = AppDef & { visibleTabs: AppTab[]; href: string };

export function visibleApps(can: (permission: string) => boolean): VisibleApp[] {
  const result: VisibleApp[] = [];
  for (const app of APPS) {
    if (app.permission && !can(app.permission)) continue;
    const visibleTabs = app.tabs.filter((t) => !t.permission || can(t.permission));
    if (app.tabs.length > 0 && visibleTabs.length === 0) continue;
    result.push({ ...app, visibleTabs, href: visibleTabs[0]?.to ?? app.to });
  }
  return result;
}

export function activeApp(apps: VisibleApp[], pathname: string): VisibleApp | undefined {
  return apps.find((a) => a.match(pathname)) ?? apps.find((a) => a.id === "home");
}

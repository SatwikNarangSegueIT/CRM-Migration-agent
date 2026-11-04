import { Link, NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../../auth/context";
import { SettingsIcon } from "../../components/icons";
import { cx } from "../../components/ui/cx";
import { useApps } from "../../lib/records";

type Item = { to: string; label: string; description: string; perms: string[]; app?: string };
const SECTIONS: { title: string; items: Item[] }[] = [
  {
    title: "Administration",
    items: [
      {
        to: "/admin/users",
        label: "Users",
        description: "Invite people, set profiles and reset sign-ins.",
        perms: ["manage_users"],
      },
      {
        to: "/setup/portal-users",
        label: "Portal Users",
        description: "Client access to the self-service portal.",
        perms: ["manage_portal_users"],
      },
      {
        to: "/admin/audit",
        label: "Audit Log",
        description: "Every sign-in, change and export, kept for review.",
        perms: ["view_audit_log"],
      },
    ],
  },
  {
    title: "Security",
    items: [
      {
        to: "/setup/profiles",
        label: "Profiles",
        description: "What each role can see and do, object by object.",
        perms: ["view_setup", "manage_profiles_sharing"],
      },
      {
        to: "/setup/roles",
        label: "Roles",
        description: "Your firm's hierarchy for record visibility.",
        perms: ["view_setup", "manage_profiles_sharing"],
      },
      {
        to: "/setup/sharing",
        label: "Sharing Settings",
        description: "Default access and sharing rules.",
        perms: ["view_setup", "manage_profiles_sharing"],
      },
      {
        to: "/setup/groups",
        label: "Public Groups & Queues",
        description: "Teams that share work and records.",
        perms: ["view_setup", "manage_profiles_sharing"],
      },
    ],
  },
  {
    title: "Platform Tools",
    items: [
      {
        to: "/setup/objects",
        label: "Object Manager",
        description: "Fields, layouts and validation rules.",
        perms: ["view_setup", "customize_application"],
      },
      {
        to: "/setup/apps",
        label: "App Manager",
        description: "Which apps and tabs people see.",
        perms: ["view_setup", "customize_application"],
      },
      {
        to: "/setup/packs",
        label: "Industry Packs",
        description: "Add another practice area to this workspace.",
        perms: ["view_setup", "manage_industry_packs"],
      },
    ],
  },
  {
    title: "Settings",
    items: [
      {
        to: "/setup/settings/company",
        label: "Company & Branding",
        description: "Firm name, ABN, address, logo and colour.",
        perms: ["view_setup", "customize_application", "manage_billing_settings"],
      },
      {
        to: "/setup/settings/billing",
        label: "Billing",
        description: "Invoice numbering, terms and tax rates.",
        perms: ["view_setup", "manage_billing_settings"],
      },
      {
        to: "/setup/settings/service",
        label: "Service Levels",
        description: "Response and resolution targets for cases.",
        app: "service",
        perms: ["view_setup", "customize_application"],
      },
      {
        to: "/setup/settings/marketing",
        label: "Marketing",
        description: "Sender details and consent rules for e-mail.",
        app: "marketing",
        perms: ["view_setup", "customize_application"],
      },
      {
        to: "/setup/settings/retention",
        label: "Data Retention",
        description: "How long closed records and files are kept.",
        perms: ["view_setup", "customize_application"],
      },
    ],
  },
  {
    title: "Data",
    items: [
      {
        to: "/import",
        label: "Import Data",
        description: "Bring in clients and records from CSV.",
        perms: ["import_data"],
      },
      {
        to: "/recycle-bin",
        label: "Recycle Bin",
        description: "Restore recently deleted records.",
        perms: [],
      },
    ],
  },
];

export function useSetupSections() {
  const { can } = useAuth();
  const apps = useApps();
  // Settings for an app the workspace has switched off (e.g. Marketing in a law firm) stay out of the way;
  // they come back when the app is switched on in App Manager.
  const active = new Set((apps.data ?? []).map((a) => a.key));
  return SECTIONS.map((s) => ({
    ...s,
    items: s.items.filter(
      (i) => (i.perms.length === 0 || i.perms.some(can)) && (!i.app || !apps.data || active.has(i.app)),
    ),
  })).filter((s) => s.items.length > 0);
}

export function SetupLayout() {
  const sections = useSetupSections();
  return (
    <div className="flex flex-col gap-4 md:flex-row">
      <nav
        aria-label="Setup"
        className="w-full flex-none rounded-lg border border-slate-200 bg-white p-2 text-sm shadow-sm md:w-60"
      >
        <NavLink
          to="/setup"
          end
          className={({ isActive }) =>
            cx(
              "mb-1 flex items-center gap-2 rounded px-3 py-2 font-semibold",
              isActive ? "bg-brand-50 text-brand-700" : "text-slate-900 hover:bg-slate-50",
            )
          }
        >
          <SettingsIcon size={16} /> Setup Home
        </NavLink>
        {sections.map((s) => (
          <div key={s.title} className="mt-2">
            <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              {s.title}
            </p>
            {s.items.map((i) => (
              <NavLink
                key={i.to}
                to={i.to}
                className={({ isActive }) =>
                  cx(
                    "block rounded px-3 py-1.5",
                    isActive
                      ? "bg-brand-50 font-semibold text-brand-700"
                      : "text-slate-700 hover:bg-slate-50",
                  )
                }
              >
                {i.label}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
      <div className="min-w-0 flex-1">
        <Outlet />
      </div>
    </div>
  );
}

export function SetupHomePage() {
  const sections = useSetupSections();
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Setup</h1>
        <p className="mt-1 text-sm text-slate-600">
          People and access, your firm's details, and how records and apps are shaped.
        </p>
      </header>
      {sections.map((s) => (
        <section key={s.title}>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">{s.title}</h2>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {s.items.map((i) => (
              <Link
                key={i.to}
                to={i.to}
                className="group rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-brand-300 hover:shadow"
              >
                <p className="font-medium text-slate-900 group-hover:text-brand-700">{i.label}</p>
                <p className="mt-1 text-sm text-slate-600">{i.description}</p>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

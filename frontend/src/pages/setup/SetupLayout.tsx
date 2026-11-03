import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../../auth/context";
import { SettingsIcon } from "../../components/icons";
import { cx } from "../../components/ui/cx";

type Item = { to: string; label: string; perms: string[] };
const SECTIONS: { title: string; items: Item[] }[] = [
  {
    title: "Administration",
    items: [
      { to: "/admin/users", label: "Users", perms: ["manage_users"] },
      { to: "/setup/portal-users", label: "Portal Users", perms: ["manage_portal_users"] },
      { to: "/admin/audit", label: "Audit Log", perms: ["view_audit_log"] },
    ],
  },
  {
    title: "Security",
    items: [
      { to: "/setup/profiles", label: "Profiles", perms: ["view_setup", "manage_profiles_sharing"] },
      { to: "/setup/roles", label: "Roles", perms: ["view_setup", "manage_profiles_sharing"] },
      { to: "/setup/sharing", label: "Sharing Settings", perms: ["view_setup", "manage_profiles_sharing"] },
      {
        to: "/setup/groups",
        label: "Public Groups & Queues",
        perms: ["view_setup", "manage_profiles_sharing"],
      },
    ],
  },
  {
    title: "Platform Tools",
    items: [
      { to: "/setup/objects", label: "Object Manager", perms: ["view_setup", "customize_application"] },
      { to: "/setup/apps", label: "App Manager", perms: ["view_setup", "customize_application"] },
      { to: "/setup/packs", label: "Industry Packs", perms: ["view_setup", "manage_industry_packs"] },
    ],
  },
  {
    title: "Settings",
    items: [
      {
        to: "/setup/settings/company",
        label: "Company & Branding",
        perms: ["view_setup", "customize_application", "manage_billing_settings"],
      },
      { to: "/setup/settings/billing", label: "Billing", perms: ["view_setup", "manage_billing_settings"] },
      {
        to: "/setup/settings/service",
        label: "Service Levels",
        perms: ["view_setup", "customize_application"],
      },
      { to: "/setup/settings/marketing", label: "Marketing", perms: ["view_setup", "customize_application"] },
      {
        to: "/setup/settings/retention",
        label: "Data Retention",
        perms: ["view_setup", "customize_application"],
      },
    ],
  },
  {
    title: "Data",
    items: [
      { to: "/import", label: "Import Data", perms: ["import_data"] },
      { to: "/recycle-bin", label: "Recycle Bin", perms: [] },
    ],
  },
];

export function useSetupSections() {
  const { can } = useAuth();
  return SECTIONS.map((s) => ({
    ...s,
    items: s.items.filter((i) => i.perms.length === 0 || i.perms.some(can)),
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
    <div>
      <div className="mb-4 rounded-lg bg-gradient-to-r from-[#032d60] to-brand-700 px-6 py-5 text-white shadow-sm">
        <h1 className="text-2xl font-semibold">Setup</h1>
        <p className="mt-1 text-sm text-blue-100">
          Shape the CRM to your business: users and access, objects and fields, apps, industry packs and
          company settings.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {sections.map((s) => (
          <section key={s.title} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="font-semibold text-slate-900">{s.title}</h2>
            <ul className="mt-2 space-y-1 text-sm">
              {s.items.map((i) => (
                <li key={i.to}>
                  <NavLink to={i.to} className="text-brand-700 hover:underline">
                    {i.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}

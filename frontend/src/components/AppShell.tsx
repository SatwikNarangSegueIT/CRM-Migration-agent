import { NavLink, Outlet } from "react-router-dom";

const NAV_ITEMS = [{ to: "/", label: "Home" }];

export function AppShell() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-4">
          <div className="flex items-center gap-2 font-semibold text-brand-700">
            <img src="/favicon.svg" alt="" className="h-7 w-7" />
            <span>MigrateCRM</span>
          </div>
          <nav aria-label="Main" className="flex gap-1">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 text-sm font-medium ${
                    isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}

import { Link, Outlet, useLocation } from "react-router-dom";
import { BackButton } from "./AppShell";
import { Logo } from "./Logo";
import { UserMenu } from "./UserMenu";

/** Where Back goes in the client portal when there's no earlier page: a record's list, else portal home. */
export function portalParent(pathname: string): string | null {
  const parts = pathname.split("/").filter(Boolean); // ["portal", ...]
  if (parts.length <= 1) return null;
  if (parts[1] === "o" && parts.length === 4) return `/portal/o/${parts[2]}`;
  return "/portal";
}

export function PortalLayout() {
  const { pathname } = useLocation();
  const back = portalParent(pathname);
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-14 max-w-4xl items-center justify-between gap-3 px-4">
          <div className="flex min-w-0 items-center gap-3">
            {back && <BackButton to={back} />}
            <Link to="/portal" className="min-w-0 truncate" aria-label="Portal home">
              <Logo />
            </Link>
          </div>
          <UserMenu accountPath="/portal/account" />
        </div>
      </header>
      <main id="main" className="relative mx-auto max-w-4xl overflow-x-clip px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}

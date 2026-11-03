import { Outlet } from "react-router-dom";
import { Logo } from "./Logo";
import { UserMenu } from "./UserMenu";

export function PortalLayout() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-14 max-w-4xl items-center justify-between px-4">
          <Logo />
          <UserMenu accountPath="/portal/account" />
        </div>
      </header>
      <main id="main" className="mx-auto max-w-4xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}

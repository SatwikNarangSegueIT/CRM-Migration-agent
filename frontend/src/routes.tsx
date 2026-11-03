import type { RouteObject } from "react-router-dom";
import {
  RedirectIfAuthenticated,
  RequireAuth,
  RequireClient,
  RequirePermission,
  RequireStaff,
} from "./auth/guards";
import { AppShell } from "./components/AppShell";
import { PortalLayout } from "./components/PortalLayout";
import { AccountPage } from "./pages/AccountPage";
import { AuditLogPage } from "./pages/admin/AuditLogPage";
import { UserCreatePage } from "./pages/admin/UserCreatePage";
import { UserDetailPage } from "./pages/admin/UserDetailPage";
import { UsersListPage } from "./pages/admin/UsersListPage";
import { AcceptInvitationPage } from "./pages/auth/AcceptInvitationPage";
import { ForgotPasswordPage } from "./pages/auth/ForgotPasswordPage";
import { LoginPage } from "./pages/auth/LoginPage";
import { MfaSetupPage } from "./pages/auth/MfaSetupPage";
import { MfaVerifyPage } from "./pages/auth/MfaVerifyPage";
import { ResetPasswordPage } from "./pages/auth/ResetPasswordPage";
import { ForbiddenPage } from "./pages/ForbiddenPage";
import { HomePage } from "./pages/HomePage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PortalHomePage } from "./pages/portal/PortalHomePage";

export const routes: RouteObject[] = [
  // Signed-out pages.
  {
    element: <RedirectIfAuthenticated />,
    children: [
      { path: "/login", element: <LoginPage /> },
      { path: "/forgot-password", element: <ForgotPasswordPage /> },
    ],
  },
  // Token links work whether or not someone is signed in on this browser.
  { path: "/reset-password", element: <ResetPasswordPage /> },
  { path: "/accept-invitation", element: <AcceptInvitationPage /> },
  // MFA steps (session exists but is not yet fully authenticated).
  { path: "/mfa", element: <MfaVerifyPage /> },
  { path: "/mfa/setup", element: <MfaSetupPage /> },

  // Client portal.
  {
    path: "/portal",
    element: (
      <RequireAuth>
        <RequireClient>
          <PortalLayout />
        </RequireClient>
      </RequireAuth>
    ),
    children: [
      { index: true, element: <PortalHomePage /> },
      { path: "account", element: <AccountPage /> },
    ],
  },

  // Staff CRM.
  {
    element: (
      <RequireAuth>
        <RequireStaff>
          <AppShell />
        </RequireStaff>
      </RequireAuth>
    ),
    children: [
      { index: true, element: <HomePage /> },
      { path: "account", element: <AccountPage /> },
      {
        path: "admin/users",
        element: <RequirePermission permission="user.manage" />,
        children: [
          { index: true, element: <UsersListPage /> },
          { path: "new", element: <UserCreatePage /> },
          { path: ":id", element: <UserDetailPage /> },
        ],
      },
      {
        path: "admin/audit",
        element: (
          <RequirePermission permission="audit.read">
            <AuditLogPage />
          </RequirePermission>
        ),
      },
      { path: "forbidden", element: <ForbiddenPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];

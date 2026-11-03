import { lazy, Suspense, type ComponentType } from "react";
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
import { Spinner } from "./components/ui/Spinner";
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
import { ObjectListPage } from "./pages/objects/ObjectListPage";
import { RecordPage } from "./pages/objects/RecordPage";
import { UnsubscribePage } from "./pages/public/UnsubscribePage";
import { SetupHomePage, SetupLayout } from "./pages/setup/SetupLayout";
import { CalendarPage, RecycleBinPage, SearchPage } from "./pages/WorkspacePages";

/**
 * Code-split pages: Setup, analytics, import and the customer portal load on first use, so the
 * initial bundle only holds the core CRM (lists, records, home) and sign-in.
 */
function lazyPage(load: () => Promise<Record<string, unknown>>, name: string) {
  const Page = lazy(async () => ({ default: (await load())[name] as ComponentType }));
  return function LazyPage() {
    return (
      <Suspense
        fallback={
          <div className="flex justify-center py-16">
            <Spinner label="Loading" />
          </div>
        }
      >
        <Page />
      </Suspense>
    );
  };
}

const DashboardPage = lazyPage(() => import("./pages/analytics/DashboardsPages"), "DashboardPage");
const DashboardsPage = lazyPage(() => import("./pages/analytics/DashboardsPages"), "DashboardsPage");
const NewReportPage = lazyPage(() => import("./pages/analytics/ReportsPages"), "NewReportPage");
const ReportPage = lazyPage(() => import("./pages/analytics/ReportsPages"), "ReportPage");
const ReportsPage = lazyPage(() => import("./pages/analytics/ReportsPages"), "ReportsPage");
const ImportPage = lazyPage(() => import("./pages/ImportPage"), "ImportPage");
const PortalHomePage = lazyPage(() => import("./pages/portal/PortalPages"), "PortalHomePage");
const PortalListPage = lazyPage(() => import("./pages/portal/PortalPages"), "PortalListPage");
const PortalNewCasePage = lazyPage(() => import("./pages/portal/PortalPages"), "PortalNewCasePage");
const PortalRecordPage = lazyPage(() => import("./pages/portal/PortalPages"), "PortalRecordPage");
const ObjectDetailPage = lazyPage(() => import("./pages/setup/ObjectManagerPages"), "ObjectDetailPage");
const ObjectManagerPage = lazyPage(() => import("./pages/setup/ObjectManagerPages"), "ObjectManagerPage");
const AppManagerPage = lazyPage(() => import("./pages/setup/PlatformPages"), "AppManagerPage");
const PacksPage = lazyPage(() => import("./pages/setup/PlatformPages"), "PacksPage");
const PortalUsersPage = lazyPage(() => import("./pages/setup/PlatformPages"), "PortalUsersPage");
const ProfileDetailPage = lazyPage(() => import("./pages/setup/SecurityPages"), "ProfileDetailPage");
const ProfilesPage = lazyPage(() => import("./pages/setup/SecurityPages"), "ProfilesPage");
const RolesPage = lazyPage(() => import("./pages/setup/SecurityPages"), "RolesPage");
const SettingsPage = lazyPage(() => import("./pages/setup/SettingsPages"), "SettingsPage");
const GroupsQueuesPage = lazyPage(() => import("./pages/setup/SharingPages"), "GroupsQueuesPage");
const SharingPage = lazyPage(() => import("./pages/setup/SharingPages"), "SharingPage");

// Permission lists mirror the server: read access to Setup pages needs View Setup or the managing permission.
const SECURITY = ["view_setup", "manage_profiles_sharing"];
const CUSTOMIZE = ["view_setup", "customize_application"];
const SETUP_ANY = [
  "view_setup",
  "manage_users",
  "customize_application",
  "manage_profiles_sharing",
  "manage_billing_settings",
  "manage_industry_packs",
  "view_audit_log",
  "manage_portal_users",
];

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
  { path: "/unsubscribe/:token", element: <UnsubscribePage /> },
  // MFA steps (session exists but is not yet fully authenticated).
  { path: "/mfa", element: <MfaVerifyPage /> },
  { path: "/mfa/setup", element: <MfaSetupPage /> },

  // Customer portal.
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
      { path: "cases/new", element: <PortalNewCasePage /> },
      { path: "o/:object", element: <PortalListPage /> },
      { path: "o/:object/:id", element: <PortalRecordPage /> },
      { path: "*", element: <NotFoundPage /> },
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
      { path: "app/:appKey", element: <HomePage /> },
      { path: "account", element: <AccountPage /> },
      { path: "o/:object", element: <ObjectListPage /> },
      { path: "o/:object/:id", element: <RecordPage /> },
      { path: "search", element: <SearchPage /> },
      { path: "calendar", element: <CalendarPage /> },
      { path: "recycle-bin", element: <RecycleBinPage /> },
      {
        path: "import",
        element: (
          <RequirePermission permission="import_data">
            <ImportPage />
          </RequirePermission>
        ),
      },
      { path: "reports", element: <ReportsPage /> },
      { path: "reports/new", element: <NewReportPage /> },
      { path: "reports/:id", element: <ReportPage /> },
      { path: "dashboards", element: <DashboardsPage /> },
      { path: "dashboards/:id", element: <DashboardPage /> },

      // Setup and administration share the Setup navigation.
      {
        element: (
          <RequirePermission permission={SETUP_ANY}>
            <SetupLayout />
          </RequirePermission>
        ),
        children: [
          { path: "setup", element: <SetupHomePage /> },
          {
            path: "admin/users",
            element: <RequirePermission permission="manage_users" />,
            children: [
              { index: true, element: <UsersListPage /> },
              { path: "new", element: <UserCreatePage /> },
              { path: ":id", element: <UserDetailPage /> },
            ],
          },
          {
            path: "admin/audit",
            element: (
              <RequirePermission permission="view_audit_log">
                <AuditLogPage />
              </RequirePermission>
            ),
          },
          {
            path: "setup/portal-users",
            element: (
              <RequirePermission permission="manage_portal_users">
                <PortalUsersPage />
              </RequirePermission>
            ),
          },
          {
            element: <RequirePermission permission={SECURITY} />,
            children: [
              { path: "setup/profiles", element: <ProfilesPage /> },
              { path: "setup/profiles/:id", element: <ProfileDetailPage /> },
              { path: "setup/roles", element: <RolesPage /> },
              { path: "setup/sharing", element: <SharingPage /> },
              { path: "setup/groups", element: <GroupsQueuesPage /> },
            ],
          },
          {
            element: <RequirePermission permission={CUSTOMIZE} />,
            children: [
              { path: "setup/objects", element: <ObjectManagerPage /> },
              { path: "setup/objects/:api", element: <ObjectDetailPage /> },
              { path: "setup/apps", element: <AppManagerPage /> },
            ],
          },
          {
            path: "setup/packs",
            element: (
              <RequirePermission permission={["view_setup", "manage_industry_packs"]}>
                <PacksPage />
              </RequirePermission>
            ),
          },
          {
            path: "setup/settings/:section",
            element: (
              <RequirePermission
                permission={["view_setup", "customize_application", "manage_billing_settings"]}
              >
                <SettingsPage />
              </RequirePermission>
            ),
          },
        ],
      },
      { path: "forbidden", element: <ForbiddenPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];

import { apiRequest } from "./client";
import type { MessageResponse, ObjectAccess, Ref } from "./types";

export type LoginState = "authenticated" | "mfa_required" | "mfa_setup_required";

export type LoginResult = {
  state: LoginState | "choose_workspace";
  workspaces?: { slug: string; name: string; domain: string }[];
};

export type MeResponse = {
  user: {
    id: string;
    email: string;
    name: string;
    profile: Ref;
    role: Ref | null;
    is_staff: boolean;
    title: string | null;
    mara_number: string | null;
    mfa_enabled: boolean;
  };
  session: {
    mfa_verified: boolean;
    mfa_setup_required: boolean;
    expires_at: string;
    recovery_codes_remaining: number | null;
  };
  system_permissions: string[];
  object_permissions: Record<string, ObjectAccess>;
  is_system_admin: boolean;
  /** Can change platform-wide settings (e-mail delivery). */
  is_platform_operator?: boolean;
};

export type MfaSetup = { secret: string; otpauth_uri: string; qr_svg_data_uri: string };
export type RecoveryCodes = { recovery_codes: string[] };
export type InvitationInfo = { email: string; name: string };

export const authApi = {
  me: (signal?: AbortSignal) => apiRequest<MeResponse>("/auth/me", { signal }),
  login: (email: string, password: string, workspace?: string) =>
    apiRequest<LoginResult>("/auth/login", {
      method: "POST",
      body: workspace ? { email, password, workspace } : { email, password },
    }),
  logout: () => apiRequest<MessageResponse>("/auth/logout", { method: "POST" }),
  verifyMfa: (code: string) => apiRequest<MeResponse>("/auth/mfa/verify", { method: "POST", body: { code } }),
  beginMfaSetup: () => apiRequest<MfaSetup>("/auth/mfa/setup", { method: "POST" }),
  enableMfa: (code: string) =>
    apiRequest<RecoveryCodes>("/auth/mfa/enable", { method: "POST", body: { code } }),
  regenerateRecoveryCodes: (password: string) =>
    apiRequest<RecoveryCodes>("/auth/mfa/recovery-codes", { method: "POST", body: { password } }),
  changePassword: (current_password: string, new_password: string) =>
    apiRequest<MessageResponse>("/auth/password/change", {
      method: "POST",
      body: { current_password, new_password },
    }),
  forgotPassword: (email: string) =>
    apiRequest<MessageResponse>("/auth/password/forgot", { method: "POST", body: { email } }),
  resetPassword: (token: string, new_password: string) =>
    apiRequest<MessageResponse>("/auth/password/reset", { method: "POST", body: { token, new_password } }),
  inspectInvitation: (token: string) =>
    apiRequest<InvitationInfo>("/auth/invitation/inspect", { method: "POST", body: { token } }),
  acceptInvitation: (token: string, password: string) =>
    apiRequest<MessageResponse>("/auth/invitation/accept", { method: "POST", body: { token, password } }),
};

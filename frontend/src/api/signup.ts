import { apiRequest } from "./client";
import type { LoginState } from "./auth";
import type { MessageResponse } from "./types";

export type DomainKey = "legal" | "migration" | "accounting" | "lending";

export type DomainOption = {
  key: DomainKey;
  label: string;
  profession: string;
  description: string;
  includes: string[];
  color?: string;
};

export type SignupBody = {
  domain: DomainKey;
  firm_name: string;
  name: string;
  email: string;
  password: string;
  abn: string | null;
  accept_terms: boolean;
  website_url: string | null;
};

export type Workspace = { slug: string; name: string; domain?: string };

export type OnboardingStep = { key: string; label: string; description: string; href: string; done: boolean };

export const signupApi = {
  domains: (signal?: AbortSignal) => apiRequest<DomainOption[]>("/signup/domains", { signal }),
  start: (body: SignupBody) => apiRequest<MessageResponse>("/signup", { method: "POST", body }),
  verify: (token: string) =>
    apiRequest<{ state: LoginState; workspace: Workspace }>("/signup/verify", {
      method: "POST",
      body: { token },
    }),
  onboarding: (signal?: AbortSignal) =>
    apiRequest<{ visible: boolean; steps: OnboardingStep[] }>("/onboarding", { signal }),
  dismissOnboarding: () =>
    apiRequest<{ visible: boolean; steps: OnboardingStep[] }>("/onboarding/dismiss", { method: "POST" }),
};

export type Role =
  | "ADMIN"
  | "PRACTICE_MANAGER"
  | "MIGRATION_AGENT"
  | "CASE_OFFICER"
  | "INTAKE_CONSULTANT"
  | "ACCOUNTS"
  | "AUDITOR"
  | "CLIENT";

export type Scope = "all" | "own" | "billing";

export type Page<T> = { items: T[]; total: number; page: number; page_size: number };

export type MessageResponse = { message: string };

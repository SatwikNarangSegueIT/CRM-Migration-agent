export const PASSWORD_MIN_LENGTH = 12;

/** Client-side readiness check only; the server enforces the full policy. */
export function passwordsReady(password: string, confirm: string): boolean {
  return password.length >= PASSWORD_MIN_LENGTH && password === confirm;
}

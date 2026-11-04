export const PASSWORD_MIN_LENGTH = 12;

// Same block-list as the server (backend/app/auth/security.py); the server enforces the full policy.
const COMMON = new Set([
  "password1234",
  "password12345",
  "password123!",
  "passw0rd1234",
  "123456789012",
  "qwertyuiop12",
  "qwerty123456",
  "iloveyou1234",
  "welcome12345",
  "letmein12345",
  "administrator",
  "changeme1234",
  "migration123",
  "australia123",
  "abc123456789",
  "111111111111",
  "000000000000",
  "aaaaaaaaaaaa",
  "123123123123",
  "monkey123456",
]);

export type PasswordCheck = { key: string; label: string; ok: boolean };

/** Live feedback while someone chooses a password (NIST SP 800-63B: length and block-lists). */
export function passwordChecks(
  password: string,
  context: { email?: string; name?: string } = {},
): PasswordCheck[] {
  const lowered = password.toLowerCase();
  const local = (context.email ?? "").split("@")[0]?.toLowerCase() ?? "";
  const nameParts = (context.name ?? "")
    .toLowerCase()
    .split(/\s+/)
    .filter((p) => p.length >= 4);
  const personal =
    (local.length >= 4 && lowered.includes(local)) || nameParts.some((p) => lowered.includes(p));
  const common = COMMON.has(lowered) || new Set(password).size < 4;
  return [
    {
      key: "length",
      label: `At least ${PASSWORD_MIN_LENGTH} characters`,
      ok: password.length >= PASSWORD_MIN_LENGTH,
    },
    { key: "common", label: "Not a common or repetitive password", ok: password.length > 0 && !common },
    { key: "personal", label: "Doesn't contain your name or e-mail", ok: password.length > 0 && !personal },
  ];
}

/** 0-4: rough strength from length and character variety, for the meter only. */
export function passwordStrength(password: string): number {
  if (!password) return 0;
  const classes = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter((r) => r.test(password)).length;
  let score = 0;
  if (password.length >= PASSWORD_MIN_LENGTH) score++;
  if (password.length >= 16) score++;
  if (classes >= 3) score++;
  if (password.length >= 20 || (classes === 4 && password.length >= 14)) score++;
  return Math.min(score, 4);
}

/** Client-side readiness check only; the server enforces the full policy. */
export function passwordsReady(
  password: string,
  confirm: string,
  context: { email?: string; name?: string } = {},
): boolean {
  return password === confirm && passwordChecks(password, context).every((c) => c.ok);
}

export function isEmail(value: string): boolean {
  return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value.trim());
}

/** Australian Business Number checksum (ATO algorithm). */
export function isValidAbn(value: string): boolean {
  const abn = value.replace(/[\s-]/g, "");
  if (!/^\d{11}$/.test(abn) || abn[0] === "0") return false;
  const weights = [10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19];
  const sum = abn
    .split("")
    .map(Number)
    .reduce((acc, d, i) => acc + (i === 0 ? d - 1 : d) * weights[i]!, 0);
  return sum % 89 === 0;
}

// The professional registration number each profession records on its people (stored as mara_number).
export type RegistrationField = {
  label: string;
  hint: string;
  digitsOnly: boolean;
  maxLength: number;
};

const FIELDS: Record<string, RegistrationField> = {
  migration: {
    label: "MARN",
    hint: "Migration Agents Registration Number (7 digits). Registered migration agents only; it is shown on service agreements.",
    digitsOnly: true,
    maxLength: 7,
  },
  accounting: {
    label: "Tax agent number",
    hint: "Registered tax agent number (8 digits). Shown on engagement letters.",
    digitsOnly: true,
    maxLength: 8,
  },
  lending: {
    label: "Credit representative number",
    hint: "ASIC credit representative number (6 or 7 digits).",
    digitsOnly: true,
    maxLength: 7,
  },
  legal: {
    label: "Practising certificate number",
    hint: "As shown on the solicitor's current practising certificate.",
    digitsOnly: false,
    maxLength: 20,
  },
};

/** The field for this profession, or null in a general CRM (no registration number is asked for). */
export function registrationField(domain: string | null | undefined): RegistrationField | null {
  return (domain && FIELDS[domain]) || null;
}

/**
 * Runtime brand colour. The Tailwind `brand-*` palette reads CSS variables (tailwind.config.ts), so the
 * workspace colour chosen at sign-up (law, migration, accounting, lending) or in Setup restyles the app
 * without a rebuild. The configured colour is the 700 shade (buttons, links); the others are mixed from it.
 */
export const DEFAULT_BRAND_COLOR = "#1449e1";
const STORAGE_KEY = "crm.brandColor";

// shade -> [mix target (255 = white, 0 = black), weight of the target]
const SHADES: Record<number, [number, number]> = {
  50: [255, 0.94],
  100: [255, 0.87],
  200: [255, 0.74],
  300: [255, 0.55],
  400: [255, 0.35],
  500: [255, 0.18],
  600: [255, 0.08],
  700: [255, 0],
  800: [0, 0.18],
  900: [0, 0.35],
};

function parseHex(hex: string): [number, number, number] | null {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return null;
  const n = parseInt(m[1]!, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export function brandShades(hex: string): Record<number, string> | null {
  const rgb = parseHex(hex);
  if (!rgb) return null;
  const out: Record<number, string> = {};
  for (const [shade, [target, w]] of Object.entries(SHADES)) {
    out[Number(shade)] = rgb.map((c) => Math.round(c + (target - c) * w)).join(" ");
  }
  return out;
}

/** Set the palette without remembering it (e.g. previewing a profession's colour during sign-up). */
export function previewBrandColor(hex: string | null | undefined): void {
  const shades = brandShades(hex || DEFAULT_BRAND_COLOR) ?? brandShades(DEFAULT_BRAND_COLOR)!;
  const style = document.documentElement.style;
  for (const [shade, rgb] of Object.entries(shades)) style.setProperty(`--brand-${shade}`, rgb);
}

export function applyBrandColor(hex: string | null | undefined): void {
  previewBrandColor(hex);
  try {
    if (hex) localStorage.setItem(STORAGE_KEY, hex);
  } catch {
    /* storage unavailable (private mode): the colour is simply re-fetched */
  }
}

/** Before the first render: last known colour, so the page doesn't flash the default blue. */
export function applyStoredBrandColor(): void {
  let stored: string | null = null;
  try {
    stored = localStorage.getItem(STORAGE_KEY);
  } catch {
    stored = null;
  }
  applyBrandColor(stored);
}

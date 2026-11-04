import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: Object.fromEntries(
          [50, 100, 200, 300, 400, 500, 600, 700, 800, 900].map((s) => [
            s,
            `rgb(var(--brand-${s}) / <alpha-value>)`,
          ]),
        ),
      },
    },
  },
  plugins: [],
} satisfies Config;

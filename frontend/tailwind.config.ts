import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          '"Inter Variable"',
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          '"Segoe UI"',
          "Roboto",
          "sans-serif",
        ],
      },
      boxShadow: {
        card: "inset 0 1px 0 0 rgb(255 255 255 / 0.7), 0 1px 2px 0 rgb(15 23 42 / 0.05), 0 2px 8px -2px rgb(15 23 42 / 0.06)",
        pop: "0 10px 30px -10px rgb(15 23 42 / 0.25), 0 4px 10px -6px rgb(15 23 42 / 0.12)",
      },
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

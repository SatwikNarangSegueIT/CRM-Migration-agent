import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef4ff",
          100: "#dae6ff",
          500: "#3a6df0",
          600: "#1f56e8",
          700: "#1449e1",
          800: "#173cb6",
          900: "#19378f",
        },
      },
    },
  },
  plugins: [],
} satisfies Config;

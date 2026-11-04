/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In development the SPA and the API share one origin through this proxy,
// matching production where /api is routed to the FastAPI service.
const apiTarget = process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: apiTarget, changeOrigin: false } },
    // Transform the app's modules when the dev server starts, not on the first page load.
    warmup: {
      clientFiles: [
        "./src/main.tsx",
        "./src/routes.tsx",
        "./src/components/AppShell.tsx",
        "./src/pages/**/*.tsx",
      ],
    },
  },
  optimizeDeps: {
    include: ["react", "react-dom", "react-dom/client", "react-router-dom", "@tanstack/react-query"],
  },
  build: { sourcemap: true },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    restoreMocks: true,
  },
});

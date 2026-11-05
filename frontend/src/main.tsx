import { QueryClientProvider } from "@tanstack/react-query";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { AuthProvider } from "./auth/AuthProvider";
import { BrandTheme } from "./components/BrandTheme";
import { ToastProvider } from "./components/ui";
import "@fontsource-variable/inter";
import "./index.css";
import { persistMetadata } from "./persistMetadata";
import { publicApi } from "./api/portal";
import { createQueryClient } from "./queryClient";
import { routes } from "./routes";
import { applyStoredBrandColor } from "./lib/theme";

applyStoredBrandColor();

const router = createBrowserRouter(routes);
const queryClient = createQueryClient();
persistMetadata(queryClient);
// Once per page load, in parallel with /auth/me (restored branding shows meanwhile).
void queryClient.prefetchQuery({
  queryKey: ["branding"],
  queryFn: publicApi.branding,
  staleTime: 10 * 60_000,
});

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("Root element #root not found");

// No <StrictMode>: in development it mounts every component twice, which cancels and re-sends every
// API request on each page load (twice the round trips). Lint rules cover what it would catch.
createRoot(rootElement).render(
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      <BrandTheme />
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </AuthProvider>
  </QueryClientProvider>,
);

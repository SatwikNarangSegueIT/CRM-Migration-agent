import { QueryClientProvider } from "@tanstack/react-query";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { AuthProvider } from "./auth/AuthProvider";
import { ToastProvider } from "./components/ui";
import "./index.css";
import { persistMetadata } from "./persistMetadata";
import { createQueryClient } from "./queryClient";
import { routes } from "./routes";

const router = createBrowserRouter(routes);
const queryClient = createQueryClient();
persistMetadata(queryClient);

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("Root element #root not found");

// No <StrictMode>: in development it mounts every component twice, which cancels and re-sends every
// API request on each page load (twice the round trips). Lint rules cover what it would catch.
createRoot(rootElement).render(
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </AuthProvider>
  </QueryClientProvider>,
);

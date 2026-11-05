import { useQuery } from "@tanstack/react-query";
import { publicApi } from "../api/portal";

export const DEFAULT_BRAND = "Segue CRM";

/** Organisation branding (name, colour, logo) - configurable in Setup, readable before sign-in. */
export function useBranding() {
  const q = useQuery({
    queryKey: ["branding"],
    queryFn: publicApi.branding,
    staleTime: 10 * 60_000,
    retry: false,
    // Fetched once at start-up (main.tsx): each component showing the brand mustn't refetch it again.
    refetchOnMount: false,
  });
  return {
    name: q.data?.name || DEFAULT_BRAND,
    primaryColor: q.data?.primary_color,
    logoUrl: q.data?.logo_url ?? null,
  };
}

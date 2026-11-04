import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { useAuth } from "../auth/context";
import { useBranding } from "../lib/branding";
import { applyBrandColor } from "../lib/theme";

/** Keeps the app's brand colour in step with the workspace's (refetched when the signed-in user changes). */
export function BrandTheme() {
  const queryClient = useQueryClient();
  const { me } = useAuth();
  const { primaryColor } = useBranding();
  const userId = me?.user.id;

  useEffect(() => {
    void queryClient.invalidateQueries({ queryKey: ["branding"] });
  }, [queryClient, userId]);

  useEffect(() => {
    if (primaryColor) applyBrandColor(primaryColor);
  }, [primaryColor]);

  return null;
}

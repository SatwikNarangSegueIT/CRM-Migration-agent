import { useState } from "react";

/**
 * Reads `token` from the URL fragment (#token=...) once, then removes the fragment from the
 * address bar so the token does not linger in history or get shared by copy/paste.
 */
export function useHashToken(): string {
  const [token] = useState(() => {
    const params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const value = params.get("token") ?? "";
    if (window.location.hash) {
      window.history.replaceState(
        window.history.state,
        "",
        window.location.pathname + window.location.search,
      );
    }
    return value;
  });
  return token;
}

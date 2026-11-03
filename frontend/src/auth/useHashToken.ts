import { useState } from "react";

// Tokens already taken from the address bar, by page path. Survives re-mounts and React StrictMode's
// double-invoked initialisers: the first read removes the fragment, later reads get the same token.
const taken = new Map<string, string>();

/** Exported for tests. */
export function readHashToken(): string {
  const path = window.location.pathname;
  const params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  const fromHash = params.get("token");
  if (fromHash) {
    taken.set(path, fromHash);
    window.history.replaceState(window.history.state, "", path + window.location.search);
  }
  return taken.get(path) ?? "";
}

/**
 * Reads `token` from the URL fragment (#token=...), then removes the fragment from the address bar so
 * the token does not linger in history or get shared by copy/paste.
 */
export function useHashToken(): string {
  const [token] = useState(readHashToken);
  return token;
}

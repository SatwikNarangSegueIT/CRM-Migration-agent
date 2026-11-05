// Keeps app metadata (apps, object describes, list views, branding) and the signed-in user (/auth/me) in
// localStorage so a page reload renders the shell and list layouts at once, and every request of the page
// starts straight away instead of after /auth/me; restored entries are marked stale and refreshed in the
// background (an ended session comes back as null and sends the person to sign in). Record data is never
// stored. Cleared on sign-out and when the session ends. The server checks every request regardless.
import type { QueryClient, QueryKey } from "@tanstack/react-query";
import { ME_QUERY_KEY } from "./queryClient";

const STORAGE_KEY = "crm.metadata.v1";
const PERSISTED_ROOTS = new Set(["meta", "list-views", "branding", ME_QUERY_KEY[0]]);
const MAX_AGE_MS = 7 * 24 * 60 * 60_000;

type Stored = { savedAt: number; entries: { key: QueryKey; data: unknown }[] };

function isPersisted(key: QueryKey): boolean {
  return typeof key[0] === "string" && PERSISTED_ROOTS.has(key[0]);
}

function read(): Stored | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Stored;
    if (!Array.isArray(parsed.entries) || Date.now() - parsed.savedAt > MAX_AGE_MS) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function clearPersistedMetadata(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // storage unavailable
  }
}

export function persistMetadata(client: QueryClient): void {
  const stored = read();
  if (stored) {
    for (const { key, data } of stored.entries) {
      if (isPersisted(key) && client.getQueryData(key) === undefined) {
        // updatedAt 0 = stale: shown immediately, refetched on first use.
        client.setQueryData(key, data, { updatedAt: 0 });
      }
    }
  }

  let timer: ReturnType<typeof setTimeout> | null = null;
  const save = () => {
    timer = null;
    const entries = client
      .getQueryCache()
      .findAll({
        predicate: (q) => isPersisted(q.queryKey) && q.state.status === "success" && q.state.data != null,
      })
      .map((q) => ({ key: q.queryKey, data: q.state.data }));
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ savedAt: Date.now(), entries }));
    } catch {
      // quota exceeded or storage unavailable: caching is best effort
    }
  };

  client.getQueryCache().subscribe((event) => {
    const key = event.query.queryKey;
    if (key[0] === ME_QUERY_KEY[0] && key[1] === ME_QUERY_KEY[1] && event.query.state.data === null) {
      // Signed out or session ended: forget this user's metadata.
      clearPersistedMetadata();
      return;
    }
    if (event.type === "updated" && isPersisted(key) && timer === null) {
      timer = setTimeout(save, 500);
    }
  });
}

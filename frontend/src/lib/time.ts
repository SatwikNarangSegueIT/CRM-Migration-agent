import { useEffect, useState } from "react";

/** "a few seconds ago" style relative time, refreshed every 30 s. */
export function useRelativeTime(timestamp: number | undefined): string {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(id);
  }, []);
  if (!timestamp) return "";
  const seconds = Math.max(0, Math.round((now - timestamp) / 1000));
  if (seconds < 45) return "a few seconds ago";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return minutes === 1 ? "a minute ago" : `${minutes} minutes ago`;
  const hours = Math.round(minutes / 60);
  return hours === 1 ? "an hour ago" : `${hours} hours ago`;
}

export function metaLine(parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" • ");
}

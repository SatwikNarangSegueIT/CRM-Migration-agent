import type { ReactNode } from "react";
import { cx } from "./cx";

export type BadgeTone = "gray" | "green" | "red" | "amber" | "blue" | "purple";

const TONES: Record<BadgeTone, string> = {
  gray: "bg-slate-100 text-slate-700",
  green: "bg-emerald-100 text-emerald-800",
  red: "bg-red-100 text-red-800",
  amber: "bg-amber-100 text-amber-900",
  blue: "bg-brand-100 text-brand-800",
  purple: "bg-violet-100 text-violet-800",
};

export function Badge({ tone = "gray", children }: { tone?: BadgeTone; children: ReactNode }) {
  return (
    <span
      className={cx("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold", TONES[tone])}
    >
      {children}
    </span>
  );
}

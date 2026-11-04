import { useCallback, useLayoutEffect, useRef, useState } from "react";
import { NavLink } from "react-router-dom";
import type { AppInfo, AppTab } from "../api/types";
import { useDismiss } from "../lib/useDismiss";
import { rememberApp, tabHref } from "../navigation";
import { ChevronDownIcon } from "./icons";
import { cx } from "./ui/cx";

const MORE_WIDTH = 96;

const tabClass = (active: boolean) =>
  cx(
    "whitespace-nowrap border-b-[3px] px-3 py-3 text-sm",
    active
      ? "border-brand-700 font-semibold text-slate-900"
      : "border-transparent text-slate-600 hover:border-slate-300 hover:text-slate-900",
  );

/**
 * An app's tabs on one line: the ones that don't fit go under "More", so every tab stays reachable on a
 * laptop screen (a tab bar that silently scrolls hides Reports and Dashboards).
 */
export function AppTabs({
  app,
  active,
  onPrefetch,
}: {
  app: AppInfo;
  active: AppTab | undefined;
  onPrefetch: (t: AppTab) => void;
}) {
  const wrap = useRef<HTMLDivElement>(null);
  const measure = useRef<HTMLDivElement>(null);
  const [fit, setFit] = useState(app.tabs.length);

  const recompute = useCallback(() => {
    const box = wrap.current;
    const row = measure.current;
    if (!box || !row) return;
    const widths = Array.from(row.children).map((c) => (c as HTMLElement).offsetWidth + 4);
    const total = widths.reduce((a, b) => a + b, 0);
    if (total <= box.clientWidth) {
      setFit(widths.length);
      return;
    }
    let used = MORE_WIDTH;
    let n = 0;
    for (const w of widths) {
      if (used + w > box.clientWidth) break;
      used += w;
      n += 1;
    }
    setFit(Math.max(n, 1));
  }, []);

  useLayoutEffect(() => {
    recompute();
    const ro = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(recompute);
    if (ro && wrap.current) ro.observe(wrap.current);
    return () => ro?.disconnect();
  }, [recompute, app.tabs]);

  const visible = app.tabs.slice(0, fit);
  const hidden = app.tabs.slice(fit);
  const link = (t: AppTab, extra = "") => (
    <NavLink
      key={tabHref(app, t)}
      to={tabHref(app, t)}
      onClick={() => rememberApp(app.key)}
      onMouseEnter={() => onPrefetch(t)}
      onFocus={() => onPrefetch(t)}
      aria-current={t === active ? "page" : undefined}
      className={cx(tabClass(t === active), extra)}
    >
      {t.label}
    </NavLink>
  );
  return (
    <div ref={wrap} className="relative min-w-0 flex-1">
      {/* Off-screen copy used only to measure each tab's width. */}
      <div ref={measure} aria-hidden="true" className="pointer-events-none invisible absolute flex gap-1">
        {app.tabs.map((t) => (
          <span key={tabHref(app, t)} className={tabClass(false)}>
            {t.label}
          </span>
        ))}
      </div>
      <nav aria-label={`${app.label} tabs`} className="flex gap-1">
        {visible.map((t) => link(t))}
        {hidden.length > 0 && <MoreTabs app={app} tabs={hidden} active={active} onPrefetch={onPrefetch} />}
      </nav>
    </div>
  );
}

function MoreTabs({
  app,
  tabs,
  active,
  onPrefetch,
}: {
  app: AppInfo;
  tabs: AppTab[];
  active: AppTab | undefined;
  onPrefetch: (t: AppTab) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useDismiss(open, ref, close);
  const current = tabs.find((t) => t === active);
  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className={cx(tabClass(Boolean(current)), "inline-flex items-center gap-1")}
      >
        {current ? current.label : "More"}
        <ChevronDownIcon size={14} />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 z-40 mt-1 min-w-44 rounded-lg border border-slate-200 bg-white py-1 text-sm shadow-xl"
        >
          {tabs.map((t) => (
            <NavLink
              key={tabHref(app, t)}
              role="menuitem"
              to={tabHref(app, t)}
              onClick={() => {
                rememberApp(app.key);
                close();
              }}
              onMouseEnter={() => onPrefetch(t)}
              className={cx(
                "block px-3 py-2 hover:bg-slate-50",
                t === active ? "font-semibold text-brand-700" : "text-slate-700",
              )}
            >
              {t.label}
            </NavLink>
          ))}
        </div>
      )}
    </div>
  );
}

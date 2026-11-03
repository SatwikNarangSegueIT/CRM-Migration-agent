import { useBranding } from "../lib/branding";

export function Logo({ className = "" }: { className?: string }) {
  const brand = useBranding();
  return (
    <span className={`flex items-center gap-2 font-semibold text-brand-700 ${className}`}>
      <img src={brand.logoUrl ?? "/favicon.svg"} alt="" className="h-7 w-7" />
      <span>{brand.name}</span>
    </span>
  );
}

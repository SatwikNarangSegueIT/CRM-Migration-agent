import { useBranding } from "../lib/branding";

export function Logo({ className = "" }: { className?: string }) {
  const brand = useBranding();
  return (
    <span className={`flex items-center gap-2 font-semibold text-brand-700 ${className}`}>
      {brand.logoUrl && <img src={brand.logoUrl} alt="" className="h-7 w-7 object-contain" />}
      <span>{brand.name}</span>
    </span>
  );
}

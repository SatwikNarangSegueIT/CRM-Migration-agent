export function Logo({ className = "" }: { className?: string }) {
  return (
    <span className={`flex items-center gap-2 font-semibold text-brand-700 ${className}`}>
      <img src="/favicon.svg" alt="" className="h-7 w-7" />
      <span>MigrateCRM</span>
    </span>
  );
}

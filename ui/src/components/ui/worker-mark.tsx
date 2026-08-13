import { cn } from "@/lib/cn";

/** Sovereign Worker mark: a layered concentric "control plane" glyph.
 *  Calm, precise, evokes observability + sovereignty (a ringed seal). */
export function WorkerMark({ size = 28, className }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      className={cn(className)}
      aria-hidden
    >
      <defs>
        <linearGradient id="swm" x1="4" y1="4" x2="28" y2="28" gradientUnits="userSpaceOnUse">
          <stop stopColor="#38bdf8" />
          <stop offset="1" stopColor="#0ea5e9" />
        </linearGradient>
      </defs>
      <circle cx="16" cy="16" r="13.5" stroke="url(#swm)" strokeWidth="1.4" opacity="0.5" />
      <circle cx="16" cy="16" r="9.5" stroke="url(#swm)" strokeWidth="1.4" opacity="0.8" />
      <circle cx="16" cy="16" r="3.4" fill="url(#swm)" />
      <path d="M16 2.5V6.5M16 25.5V29.5M2.5 16H6.5M25.5 16H29.5" stroke="url(#swm)" strokeWidth="1.2" opacity="0.55" />
    </svg>
  );
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <WorkerMark size={26} />
      <div className="leading-none">
        <div className="text-[13px] font-semibold tracking-wide text-ink-0">Sovereign</div>
        <div className="text-[10px] font-medium uppercase tracking-[0.22em] text-ink-3">Worker</div>
      </div>
    </div>
  );
}

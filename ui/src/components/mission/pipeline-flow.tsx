"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/cn";

const STAGES = [
  { key: "PLAN", label: "Plan" },
  { key: "EXECUTE", label: "Execute" },
  { key: "OBSERVE", label: "Observe" },
  { key: "VERIFY", label: "Verify" },
  { key: "PROVE", label: "Prove" },
] as const;

/** The signature architecture strip: PLAN → EXECUTE → OBSERVE → VERIFY → PROVE.
 *  Calm sequential illumination; honors reduced-motion via CSS. */
export function PipelineFlow({ compact = false }: { compact?: boolean }) {
  return (
    <div className={cn("flex items-center gap-1.5", compact ? "text-[12px]" : "text-sm")}>
      {STAGES.map((s, i) => (
        <div key={s.key} className="flex items-center">
          <div className="flex flex-col items-center gap-1.5">
            <motion.div
              initial={{ opacity: 0.35 }}
              animate={{ opacity: 1 }}
              transition={{ delay: i * 0.18, duration: 0.5 }}
              className={cn(
                "grid place-items-center rounded-md border px-3 py-1.5 font-medium tracking-wide",
                i === STAGES.length - 1
                  ? "border-accent/40 bg-accent/10 text-accent"
                  : "border-hairline-soft bg-surface-2 text-ink-1",
              )}
            >
              {s.label}
            </motion.div>
          </div>
          {i < STAGES.length - 1 ? (
            <motion.div
              aria-hidden
              initial={{ scaleX: 0, opacity: 0 }}
              animate={{ scaleX: 1, opacity: 1 }}
              transition={{ delay: i * 0.18 + 0.12, duration: 0.35 }}
              className="mx-1 h-px w-5 origin-left bg-gradient-to-r from-accent/60 to-ink-4 md:w-8"
            />
          ) : null}
        </div>
      ))}
    </div>
  );
}

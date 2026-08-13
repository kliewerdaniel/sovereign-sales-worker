"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { cn } from "@/lib/cn";
import { NAV } from "@/lib/nav";
import { Wordmark } from "@/components/ui/worker-mark";
import { Badge } from "@/components/ui/primitives";
import { useBackend } from "@/components/providers/backend-provider";

export function Sidebar() {
  const pathname = usePathname();
  const backend = useBackend();

  return (
    <aside className="flex h-full w-[248px] shrink-0 flex-col border-r border-hairline-soft bg-surface-0/80">
      <div className="flex h-14 items-center border-b border-hairline-soft px-4">
        <Link href="/" aria-label="Sovereign Worker home">
          <Wordmark />
        </Link>
      </div>

      <nav className="flex-1 overflow-y-auto px-2.5 py-3" aria-label="Primary">
        <ul className="space-y-0.5">
          {NAV.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    "group relative flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors",
                    active ? "text-ink-0" : "text-ink-2 hover:text-ink-1 hover:bg-surface-3/50",
                  )}
                  aria-current={active ? "page" : undefined}
                >
                  {active ? (
                    <motion.span
                      layoutId="nav-active"
                      className="absolute inset-0 rounded-md border border-hairline bg-surface-2"
                      transition={{ type: "spring", stiffness: 380, damping: 32 }}
                    />
                  ) : null}
                  <Icon className={cn("relative z-10 h-4 w-4", active ? "text-accent" : "text-ink-3")} />
                  <span className="relative z-10 font-medium">{item.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="border-t border-hairline-soft px-3.5 py-3">
        <div className="flex items-center justify-between text-[11px] text-ink-3">
          <span>Runtime</span>
          <Badge tone="ok" className="px-1.5 py-0.5">
            <span className="h-1.5 w-1.5 rounded-full bg-ok live-dot" /> online
          </Badge>
        </div>
        <div className="mt-2 flex items-center justify-between text-[11px] text-ink-3">
          <span>Backend</span>
          <Badge tone={backend.source === "live" ? "accent" : "neutral"} className="px-1.5 py-0.5">
            {backend.source === "live" ? "live" : "demo"}
          </Badge>
        </div>
      </div>
    </aside>
  );
}

"use client";

import { useBackend } from "@/components/providers/backend-provider";
import { Info } from "lucide-react";

export function DemoNotice() {
  const backend = useBackend();
  if (backend.source === "live") return null;
  return (
    <div className="flex items-center gap-2 border-b border-block/30 bg-block/10 px-4 py-1.5 text-xs text-block">
      <Info className="h-3.5 w-3.5 shrink-0" />
      <span className="font-medium">DEMO</span>
      <span className="text-ink-2">
        Viewing a deterministic demonstration dataset that mirrors the live <span className="mono text-ink-1">/api/v1</span> contract. Not a live workspace.
      </span>
    </div>
  );
}

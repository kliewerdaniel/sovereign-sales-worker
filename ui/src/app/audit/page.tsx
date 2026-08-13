"use client";

import { useBackend } from "@/components/providers/backend-provider";
import { useAsync } from "@/lib/use-async";
import { Badge, EmptyState, Hash, StatusDot } from "@/components/ui/primitives";
import { fmtTime, TONE_CLASS } from "@/lib/domain";
import type { Tone } from "@/lib/domain";
import { cn } from "@/lib/cn";
import { Inbox, ShieldAlert } from "lucide-react";

const SEVERITY_TONE: Record<string, Tone> = {
  notice: "ok",
  info: "neutral",
  warning: "warn",
  critical: "bad",
};

export default function AuditPage() {
  const backend = useBackend();
  const { data, loading } = useAsync(() => backend.getSecurityEvents(), []);

  const chain = data?.chain;
  const events = data?.events ?? [];

  return (
    <div className="mx-auto max-w-7xl px-5 py-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-ink-0">Audit</h1>
        <p className="mt-1 text-sm text-ink-3">
          The tamper-evident trail. Every write is hash-chained — replay reconstructs a run without re-running the model.
        </p>
      </div>

      {chain ? (
        <div className={cn("mt-5 flex items-center gap-3 rounded-lg border px-4 py-3")}>
          <StatusDot tone={chain.ok ? "ok" : "bad"} />
          <div className="text-sm">
            <span className="font-medium text-ink-0">Integrity chain {chain.ok ? "intact" : "BROKEN"}</span>
            <span className="ml-2 text-ink-3">
              {chain.checked} entries verified · {chain.lines} lines
            </span>
          </div>
          <Badge tone={chain.ok ? "ok" : "bad"} className="ml-auto">
            {chain.ok ? "verified" : "alert"}
          </Badge>
        </div>
      ) : null}

      <div className="mt-6">
        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="text-sm font-semibold tracking-wide text-ink-1">Security events</h2>
          <span className="text-xs text-ink-3">{events.length} recorded</span>
        </div>

        {!loading && events.length === 0 ? (
          <EmptyState icon={<Inbox className="h-8 w-8" />} title="No security events" body="Policy blocks, approvals, and verifications appear here." />
        ) : loading ? (
          [0, 1, 2].map((i) => <div key={i} className="surface h-[72px] animate-pulse" />)
        ) : (
          <div className="space-y-2">
            {events.map((e, i) => (
              <div key={i} className="surface flex items-start gap-3 px-4 py-3">
                <span className={cn("mt-0.5 rounded-md border p-1.5", TONE_CLASS[SEVERITY_TONE[e.severity] ?? "neutral"].border, TONE_CLASS[SEVERITY_TONE[e.severity] ?? "neutral"].bg)}>
                  <ShieldAlert className={cn("h-4 w-4", TONE_CLASS[SEVERITY_TONE[e.severity] ?? "neutral"].text)} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-ink-0">{e.label}</span>
                    <Badge tone={SEVERITY_TONE[e.severity] ?? "neutral"}>{e.severity}</Badge>
                    <span className="mono text-[11px] text-ink-3">{e.kind}</span>
                    <span className="ml-auto text-[11px] text-ink-3">{fmtTime(e.ts)}</span>
                  </div>
                  <p className="mt-1 text-[13px] leading-relaxed text-ink-3">{e.summary}</p>
                  <div className="mt-1 flex items-center gap-1.5 text-[11px] text-ink-4">
                    actor <Hash value={e.actor} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

"use client";

import { useBackend } from "@/components/providers/backend-provider";
import { useAsync } from "@/lib/use-async";
import { Badge, EmptyState, RiskBadge } from "@/components/ui/primitives";
import { RISK_LABEL } from "@/lib/domain";
import type { Tone } from "@/lib/domain";
import { RISK_ORDER } from "@/lib/types";
import type { PolicyValue, RiskLevel } from "@/lib/types";
import { cn } from "@/lib/cn";
import { ShieldCheck, Inbox, Lock } from "lucide-react";

const POLICY_TONE: Record<PolicyValue, Tone> = {
  auto: "ok",
  approve: "warn",
  deny: "bad",
};

const POLICY_HELP: Record<PolicyValue, string> = {
  auto: "Allowed without review.",
  approve: "Requires human approval before execution.",
  deny: "Blocked by default — never executes.",
};

export default function PolicyPage() {
  const backend = useBackend();
  const { data: workers, loading } = useAsync(() => backend.listWorkers(), []);

  return (
    <div className="mx-auto max-w-7xl px-5 py-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-ink-0">Policy</h1>
        <p className="mt-1 text-sm text-ink-3">
          What each worker is allowed to do. Policy is a version-controlled YAML file the model cannot edit.
          Default-deny: anything not explicitly permitted is blocked.
        </p>
      </div>

      <div className="mt-5 space-y-5">
        {!loading && (!workers || workers.length === 0) ? (
          <EmptyState icon={<Inbox className="h-8 w-8" />} title="No workers configured" body="Worker configs define the policy boundary." />
        ) : loading ? (
          [0, 1].map((i) => <div key={i} className="surface h-[260px] animate-pulse" />)
        ) : (
          (workers ?? []).map((w) => (
            <div key={w.name} className="surface p-5">
              <div className="flex flex-wrap items-center gap-3">
                <span className="rounded-md border border-hairline-soft bg-surface-3/40 p-1.5 text-accent">
                  <ShieldCheck className="h-4 w-4" />
                </span>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm text-ink-0">{w.name}</span>
                    {w.disabled ? <Badge tone="bad">disabled</Badge> : null}
                  </div>
                  <p className="text-xs text-ink-3">{w.role}</p>
                </div>
                <div className="ml-auto flex flex-wrap items-center gap-1.5 text-[11px] text-ink-3">
                  <Lock className="h-3.5 w-3.5" />
                  egress allow-list: {w.egress_allow.length === 0 ? <Badge tone="bad">empty (deny)</Badge> : <span>{w.egress_allow.length} entries</span>}
                </div>
              </div>

              <div className="mt-4">
                <div className="mb-2 text-[11px] uppercase tracking-wider text-ink-3">Risk policy</div>
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
                  {RISK_ORDER.map((risk: RiskLevel) => {
                    const pv = w.policy[risk] as PolicyValue;
                    return (
                      <div key={risk} className="rounded-md border border-hairline-soft bg-surface-1 p-3">
                        <div className="flex items-center justify-between">
                          <RiskBadge risk={risk} />
                        </div>
                        <div className="mt-2">
                          <Badge tone={POLICY_TONE[pv]} className="capitalize">
                            {pv}
                          </Badge>
                        </div>
                        <div className="mt-1.5 text-[11px] leading-snug text-ink-3">{POLICY_HELP[pv]}</div>
                        <div className="mt-1 text-[10px] text-ink-4">{RISK_LABEL[risk]}</div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <div>
                  <div className="mb-1.5 text-[11px] uppercase tracking-wider text-ink-3">Tools available</div>
                  <div className="flex flex-wrap gap-1.5">
                    {w.tools.length === 0 ? (
                      <span className="text-xs text-ink-4">none</span>
                    ) : (
                      w.tools.map((t) => (
                        <span key={t} className="mono rounded border border-hairline-soft bg-surface-3/40 px-1.5 py-0.5 text-[11px] text-ink-2">
                          {t}
                        </span>
                      ))
                    )}
                  </div>
                </div>
                <div>
                  <div className="mb-1.5 text-[11px] uppercase tracking-wider text-ink-3">Boundary</div>
                  <div className="space-y-1 text-[11px] text-ink-3">
                    <div>fs_roots: <span className="mono text-ink-2">{w.fs_roots.join(", ") || "—"}</span></div>
                    <div>shell_allow: <span className="mono text-ink-2">{w.shell_allow.length ? w.shell_allow.join(", ") : "—"}</span></div>
                    <div>max_steps: <span className="mono text-ink-2">{w.max_steps}</span> · max_runtime: <span className="mono text-ink-2">{w.max_runtime}s</span></div>
                    <div>sandbox: <span className="mono text-ink-2">{w.sandbox}</span></div>
                  </div>
                </div>
              </div>

              <div className="mt-3 border-t border-hairline-soft pt-3 text-[11px] text-ink-4">
                config: <span className="mono">{w.path}</span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

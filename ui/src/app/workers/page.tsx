"use client";

import { useBackend } from "@/components/providers/backend-provider";
import { useAsync } from "@/lib/use-async";
import { Badge, EmptyState, RiskBadge } from "@/components/ui/primitives";
import { RISK_LABEL } from "@/lib/domain";
import { cn } from "@/lib/cn";
import { Boxes, Inbox } from "lucide-react";
import type { WorkerConfig, RiskLevel } from "@/lib/types";

export default function WorkersPage() {
  const backend = useBackend();
  const { data, loading } = useAsync(() => backend.listWorkers(), []);

  const workers = data ?? [];

  return (
    <div className="mx-auto max-w-7xl px-5 py-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-ink-0">Workers</h1>
        <p className="mt-1 text-sm text-ink-3">
          Identities with a role, a knowledge base, and a policy boundary. Each is a configured, version-controlled agent.
        </p>
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-2">
        {!loading && workers.length === 0 ? (
          <div className="md:col-span-2">
            <EmptyState icon={<Inbox className="h-8 w-8" />} title="No workers" body="Workers are defined in version-controlled YAML configs." />
          </div>
        ) : loading ? (
          [0, 1].map((i) => <div key={i} className="surface h-[220px] animate-pulse" />)
        ) : (
          workers.map((w) => <WorkerCard key={w.name} w={w} />)
        )}
      </div>
    </div>
  );
}

function WorkerCard({ w }: { w: WorkerConfig }) {
  const maxRisk = (Object.entries(w.policy) as Array<[RiskLevel, string]>)
    .filter(([, v]) => v !== "deny")
    .map(([r]) => r);
  return (
    <div className="surface p-5">
      <div className="flex items-start gap-3">
        <span className="rounded-md border border-hairline-soft bg-surface-3/40 p-2 text-accent">
          <Boxes className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm text-ink-0">{w.name}</span>
            {w.disabled ? <Badge tone="bad">disabled</Badge> : <Badge tone="ok">active</Badge>}
          </div>
          <p className="text-xs text-ink-3">{w.role}</p>
        </div>
      </div>

      <p className="mt-3 text-[13px] leading-relaxed text-ink-2">{w.instructions}</p>

      <div className="mt-4">
        <div className="mb-1.5 text-[11px] uppercase tracking-wider text-ink-3">Highest permitted risk</div>
        <div className="flex flex-wrap gap-1.5">
          {maxRisk.length === 0 ? (
            <Badge tone="ok">read only</Badge>
          ) : (
            maxRisk.map((r) => <RiskBadge key={r} risk={r} />)
          )}
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <Stat label="Tools" value={String(w.tools.length)} />
        <Stat label="Procedures" value={String(w.procedures.length)} />
        <Stat label="Knowledge" value={String(w.knowledge.length)} />
      </div>

      <div className="mt-3 border-t border-hairline-soft pt-3 text-[11px] text-ink-4">
        config: <span className="mono">{w.path}</span>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-hairline-soft bg-surface-1 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-ink-3">{label}</div>
      <div className="mono text-lg font-semibold text-ink-0">{value}</div>
    </div>
  );
}

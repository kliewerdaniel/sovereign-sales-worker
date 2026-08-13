"use client";

import { useMemo, useState } from "react";
import { useBackend } from "@/components/providers/backend-provider";
import { useAsync } from "@/lib/use-async";
import { Badge, EmptyState, RiskBadge } from "@/components/ui/primitives";
import { cn } from "@/lib/cn";
import { Hammer, Inbox } from "lucide-react";
import type { ToolSpec, RiskLevel } from "@/lib/types";

export default function ToolsPage() {
  const backend = useBackend();
  const { data, loading } = useAsync(() => backend.listTools(), []);
  const [open, setOpen] = useState<string | null>(null);

  const tools = data ?? [];

  return (
    <div className="mx-auto max-w-7xl px-5 py-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-ink-0">Tools</h1>
        <p className="mt-1 text-sm text-ink-3">
          The worker&apos;s interface to the world. Each tool declares its risk level and approval requirement &mdash;
          the boundary the policy enforces.
        </p>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {!loading && tools.length === 0 ? (
          <div className="md:col-span-2 xl:col-span-3">
            <EmptyState icon={<Inbox className="h-8 w-8" />} title="No tools registered" body="The tool registry is empty." />
          </div>
        ) : loading ? (
          [0, 1, 2, 3, 4, 5].map((i) => <div key={i} className="surface h-[150px] animate-pulse" />)
        ) : (
          tools.map((t) => <ToolCard key={t.name} t={t} open={open === t.name} onToggle={() => setOpen(open === t.name ? null : t.name)} />)
        )}
      </div>
    </div>
  );
}

function ToolCard({ t, open, onToggle }: { t: ToolSpec; open: boolean; onToggle: () => void }) {
  const callRate = (t.calls ?? 0) > 0 ? Math.round(((t.failures ?? 0) / (t.calls ?? 1)) * 100) : 0;
  return (
    <div className="surface overflow-hidden">
      <button onClick={onToggle} className="flex w-full items-start gap-3 px-4 py-3.5 text-left">
        <span className="mt-0.5 rounded-md border border-hairline-soft bg-surface-3/40 p-1.5 text-accent">
          <Hammer className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="mono truncate text-sm text-ink-0">{t.name}</span>
            {t.requires_approval ? <Badge tone="warn">approval</Badge> : <Badge tone="ok">auto</Badge>}
          </div>
          <p className="mt-1 line-clamp-2 text-[13px] leading-snug text-ink-3">{t.description}</p>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <RiskBadge risk={t.risk_level as RiskLevel} />
            {t.reversible ? <Badge tone="neutral">reversible</Badge> : <Badge tone="bad">irreversible</Badge>}
          </div>
        </div>
      </button>

      {open ? (
        <div className="border-t border-hairline-soft px-4 py-3 text-[12px]">
          <div className="grid grid-cols-2 gap-x-4 gap-y-2">
            <Field label="Calls" value={String(t.calls ?? 0)} />
            <Field label="Failures" value={`${t.failures ?? 0} (${callRate}%)`} />
            <Field label="Evidence produced" value={String(t.evidence ?? 0)} />
            <Field label="Last used" value={t.last_used ? new Date(t.last_used * 1000).toISOString().slice(11, 19) : "—"} />
          </div>
          <div className="mt-2.5">
            <div className="mb-1 text-[11px] uppercase tracking-wider text-ink-3">Permissions</div>
            <div className="flex flex-wrap gap-1.5">
              {(t.permissions ?? []).length === 0 ? (
                <span className="text-ink-4">none</span>
              ) : (
                (t.permissions ?? []).map((p) => (
                  <span key={p} className="mono rounded border border-hairline-soft bg-surface-3/40 px-1.5 py-0.5 text-[10px] text-ink-2">{p}</span>
                ))
              )}
            </div>
          </div>
          <div className="mt-2.5">
            <div className="mb-1 text-[11px] uppercase tracking-wider text-ink-3">Input schema</div>
            <pre className="overflow-x-auto rounded-md border border-hairline-soft bg-surface-0 p-2.5 font-mono text-[11px] text-ink-2">
              {JSON.stringify(t.input_schema, null, 2)}
            </pre>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-ink-3">{label}</div>
      <div className="mono text-ink-1">{value}</div>
    </div>
  );
}

"use client";

import { useBackend } from "@/components/providers/backend-provider";
import { Badge, StatusDot, SectionTitle } from "@/components/ui/primitives";
import { GitBranch, Database, ShieldCheck, Sparkles } from "lucide-react";

export default function SettingsPage() {
  const backend = useBackend();
  const isLive = backend.source === "live";

  return (
    <div className="mx-auto max-w-3xl px-5 py-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-ink-0">Settings</h1>
        <p className="mt-1 text-sm text-ink-3">Backend connection and appearance.</p>
      </div>

      <div className="mt-5 space-y-4">
        <div className="surface p-5">
          <SectionTitle hint="data source">Backend</SectionTitle>
          <div className="flex items-center gap-3">
            <StatusDot tone={isLive ? "accent" : "ok"} />
            <span className="text-sm font-medium text-ink-0">
              {isLive ? "Live runtime" : "Demo dataset"}
            </span>
            <Badge tone={isLive ? "accent" : "neutral"}>{backend.source}</Badge>
          </div>
          <p className="mt-2 text-[13px] leading-relaxed text-ink-3">
            {isLive
              ? "Connected to a live sovereign-worker runtime at the configured API base. All data is read from the real ledger."
              : "Showing a deterministic demonstration dataset that mirrors the live /api/v1 contract exactly. Nothing here is presented as a real workspace."}
          </p>
          <p className="mt-2 text-[12px] text-ink-4">
            Swap to a live backend by setting <code className="mono rounded bg-surface-3/60 px-1 py-0.5">NEXT_PUBLIC_SOVEREIGN_API_BASE</code> and restarting.
          </p>
        </div>

        <div className="surface p-5">
          <SectionTitle>Philosophy</SectionTitle>
          <p className="text-[13px] leading-relaxed text-ink-2">
            <span className="font-medium text-ink-0">Autonomous does not have to mean opaque.</span> AI workers can be
            powerful while remaining inspectable, evidence-driven, and under human control. Every screen in this console
            is built to make the worker&apos;s decisions traceable to source.
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <Legend icon={<Database className="h-4 w-4" />} title="Evidence-first" body="No claim exists without a source_ref. Hypothesis is shown distinctly from observed fact." />
          <Legend icon={<ShieldCheck className="h-4 w-4" />} title="Human in the loop" body="Egress and financial actions require explicit approval. The default is deny." />
          <Legend icon={<GitBranch className="h-4 w-4" />} title="Replayable" body="The audit trail is hash-chained — any run can be reconstructed without re-running the model." />
          <Legend icon={<Sparkles className="h-4 w-4" />} title="Version-controlled" body="Policy ships in diffable YAML the model cannot edit." />
        </div>
      </div>
    </div>
  );
}

function Legend({ icon, title, body }: { icon: React.ReactNode; title: string; body: string }) {
  return (
    <div className="surface flex gap-3 p-4">
      <span className="mt-0.5 rounded-md border border-hairline-soft bg-surface-3/40 p-1.5 text-accent">{icon}</span>
      <div>
        <div className="text-sm font-medium text-ink-0">{title}</div>
        <p className="mt-0.5 text-[12px] leading-relaxed text-ink-3">{body}</p>
      </div>
    </div>
  );
}

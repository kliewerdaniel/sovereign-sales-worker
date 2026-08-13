"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useBackend } from "@/components/providers/backend-provider";
import { useAsync } from "@/lib/use-async";
import { Badge, EmptyState, OutreachBadge, TierBadge } from "@/components/ui/primitives";
import { fmtTime } from "@/lib/domain";
import type { Tone } from "@/lib/domain";
import { cn } from "@/lib/cn";
import { Users, Inbox, TrendingUp } from "lucide-react";
import type { LeadDetail, SalesLead, PipelineStage, Qualification } from "@/lib/types";

const STAGE_ORDER: PipelineStage[] = [
  "prospect", "contacted", "responded", "discovery_scheduled", "discovery_completed",
  "qualified", "audit_in_progress", "proposal_sent", "negotiation", "won", "lost",
  "onboarding", "implementation", "completed", "expansion",
];

const STAGE_TONE: Record<PipelineStage, Tone> = {
  prospect: "neutral",
  contacted: "neutral",
  responded: "accent",
  discovery_scheduled: "accent",
  discovery_completed: "accent",
  qualified: "ok",
  audit_in_progress: "warn",
  proposal_sent: "warn",
  negotiation: "warn",
  won: "ok",
  lost: "bad",
  onboarding: "ok",
  implementation: "ok",
  completed: "ok",
  expansion: "accent",
};

function bandOf(score: number): { label: string; tone: Tone } {
  if (score >= 60) return { label: "High", tone: "ok" };
  if (score >= 40) return { label: "Medium", tone: "warn" };
  if (score > 0) return { label: "Low", tone: "neutral" };
  return { label: "Insufficient", tone: "bad" };
}

export default function ProspectsPage() {
  const backend = useBackend();
  const { data, loading } = useAsync(() => backend.listLeads(), []);
  const [q, setQ] = useState("");

  const leads = data ?? [];
  const filtered = useMemo(() => {
    let out = leads;
    if (q.trim()) {
      const needle = q.toLowerCase();
      out = out.filter((l: SalesLead) =>
        `${l.id} ${l.company_name ?? ""} ${l.industry ?? ""} ${l.stage}`.toLowerCase().includes(needle),
      );
    }
    return [...out].sort((a, b) => b.score - a.score);
  }, [leads, q]);

  const highCount = leads.filter((l) => l.score >= 60).length;

  return (
    <div className="mx-auto max-w-7xl px-5 py-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-ink-0">Prospects</h1>
          <p className="mt-1 text-sm text-ink-3">
            The sales pipeline. Scores are deterministic and re-derivable from evidence — no black box.
          </p>
        </div>
        <div className="relative w-full max-w-xs">
          <Users className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search prospects…"
            className="w-full rounded-md border border-hairline-soft bg-surface-1 py-2 pl-9 pr-3 text-sm text-ink-0 outline-none placeholder:text-ink-3 focus:border-hairline"
            aria-label="Search prospects"
          />
        </div>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        <div className="surface px-3.5 py-3">
          <div className="text-[11px] uppercase tracking-wider text-ink-3">Total prospects</div>
          <div className="mt-1 text-2xl font-semibold tabular-nums text-ink-0">{leads.length}</div>
        </div>
        <div className="surface px-3.5 py-3">
          <div className="text-[11px] uppercase tracking-wider text-ink-3">High-fit (≥60)</div>
          <div className="mt-1 flex items-center gap-2 text-2xl font-semibold tabular-nums text-ok">
            <TrendingUp className="h-5 w-5" /> {highCount}
          </div>
        </div>
        <div className="surface px-3.5 py-3">
          <div className="text-[11px] uppercase tracking-wider text-ink-3">Avg score</div>
          <div className="mt-1 text-2xl font-semibold tabular-nums text-ink-0">
            {leads.length ? (leads.reduce((s, l) => s + l.score, 0) / leads.length).toFixed(1) : "—"}
          </div>
        </div>
      </div>

      <div className="mt-4 space-y-2.5">
        {!loading && filtered.length === 0 ? (
          <EmptyState icon={<Inbox className="h-8 w-8" />} title="No prospects" body="The pipeline is empty for this filter." />
        ) : loading ? (
          [0, 1, 2].map((i) => <div key={i} className="surface h-[96px] animate-pulse" />)
        ) : (
          filtered.map((l) => <LeadRow key={l.id} l={l} />)
        )}
      </div>
    </div>
  );
}

function LeadRow({ l }: { l: SalesLead }) {
  const band = bandOf(l.score);
  const detail: LeadDetail | null = (l as unknown as LeadDetail).qualifications ? (l as unknown as LeadDetail) : null;
  const qual: Qualification | undefined = detail?.qualifications?.[0];
  return (
    <Link href={`/prospects/${l.id}`}>
      <div className="surface flex flex-wrap items-center gap-4 px-4 py-3 transition-colors hover:border-hairline">
        <div className="min-w-[52px] text-center">
          <div className="text-2xl font-semibold tabular-nums text-ink-0">{l.score.toFixed(1)}</div>
          <Badge tone={band.tone} className="mt-0.5">{band.label}</Badge>
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="font-medium text-ink-0">{l.company_name ?? l.id}</span>
            {l.industry ? <span className="text-xs text-ink-3">{l.industry}</span> : null}
            <Badge tone={STAGE_TONE[l.stage]}>{l.stage.replace(/_/g, " ")}</Badge>
          </div>
          <p className="mt-1 text-[13px] text-ink-3">{l.next_action}</p>
          {qual ? (
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              {(["icp_fit", "pain_signal", "urgency", "economic_potential", "accessibility", "confidence"] as const).map((k) =>
                qual[k] ? (
                  <span key={k} className="mono rounded border border-hairline-soft bg-surface-3/40 px-1.5 py-0.5 text-[10px] text-ink-2">
                    {k.replace(/_/g, " ").slice(0, 4)} {qual[k]}
                  </span>
                ) : null,
              )}
            </div>
          ) : null}
        </div>
        <div className="hidden w-32 text-right text-[11px] text-ink-3 sm:block">
          owner <span className="text-ink-2">{l.owner}</span>
        </div>
        <div className="w-8 text-right text-ink-3 transition-transform group-hover:translate-x-0.5">→</div>
      </div>
    </Link>
  );
}

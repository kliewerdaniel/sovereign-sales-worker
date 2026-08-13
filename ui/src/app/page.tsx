"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { useBackend } from "@/components/providers/backend-provider";
import { useAsync } from "@/lib/use-async";
import { PipelineFlow } from "@/components/mission/pipeline-flow";
import { Card, Metric, RunStatusBadge, SectionTitle, StatusDot } from "@/components/ui/primitives";
import { fmtDuration, fmtTime } from "@/lib/domain";
import { ArrowRight, Boxes, CheckCircle2, FileText, ShieldCheck, Sparkles, GitBranch } from "lucide-react";
import type { RunRecord } from "@/lib/types";

export default function MissionControlPage() {
  const backend = useBackend();
  const { data, loading } = useAsync(() => backend.getDashboard(), []);

  return (
    <div className="mx-auto max-w-7xl px-5 py-6">
      {/* Hero / identity */}
      <section className="surface relative overflow-hidden px-6 py-7">
        <div className="absolute right-0 top-0 h-40 w-72 bg-accent-glow blur-2xl" aria-hidden />
        <div className="relative flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="text-[11px] font-medium uppercase tracking-[0.22em] text-accent">Sovereign Worker</div>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-ink-0">
              Policy-controlled autonomous workers.
            </h1>
            <p className="mt-2 max-w-xl text-sm leading-relaxed text-ink-2">
              Autonomous does not have to mean opaque. Every worker is inspectable, evidence-driven, and
              held under human control — from the first request to the final audit hash.
            </p>
            <div className="mt-4">
              <PipelineFlow />
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2 rounded-md border border-hairline-soft bg-surface-2/60 px-3 py-2 text-xs text-ink-2">
            <ShieldCheck className="h-4 w-4 text-ok" />
            <span>Human-in-the-loop egress · hash-chained ledger · default-deny</span>
          </div>
        </div>
      </section>

      {/* Runtime status */}
      <section className="mt-6">
        <SectionTitle hint="live status">Runtime status</SectionTitle>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
          <Card>
            <div className="flex items-center gap-2 text-xs text-ink-3">
              <StatusDot tone="ok" pulse /> Worker
            </div>
            <div className="mt-1.5 text-lg font-semibold text-ink-0">sales_researcher</div>
            <div className="text-xs text-ink-3">online · idle</div>
          </Card>
          <Card>
            <div className="flex items-center gap-2 text-xs text-ink-3">
              <Boxes className="h-3.5 w-3.5" /> Tools
            </div>
            <div className="mt-1.5 text-lg font-semibold text-ink-0">6</div>
            <div className="text-xs text-ink-3">available</div>
          </Card>
          <Card>
            <div className="flex items-center gap-2 text-xs text-ink-3">
              <ShieldCheck className="h-3.5 w-3.5" /> Policy
            </div>
            <div className="mt-1.5 text-lg font-semibold text-ok">enforced</div>
            <div className="text-xs text-ink-3">default-deny egress</div>
          </Card>
          <Card>
            <div className="flex items-center gap-2 text-xs text-ink-3">
              <CheckCircle2 className="h-3.5 w-3.5" /> Pending approvals
            </div>
            <div className="mt-1.5 text-lg font-semibold text-block">{data?.pending_approvals ?? 1}</div>
            <div className="text-xs text-ink-3">awaiting human</div>
          </Card>
          <Card>
            <div className="flex items-center gap-2 text-xs text-ink-3">
              <GitBranch className="h-3.5 w-3.5" /> Active runs
            </div>
            <div className="mt-1.5 text-lg font-semibold text-ink-0">1</div>
            <div className="text-xs text-ink-3">sales_outreach</div>
          </Card>
          <Card>
            <div className="flex items-center gap-2 text-xs text-ink-3">
              <Sparkles className="h-3.5 w-3.5" /> Model
            </div>
            <div className="mt-1.5 text-lg font-semibold text-ink-0">ready</div>
            <div className="text-xs text-ink-3">local-runtime</div>
          </Card>
        </div>
      </section>

      {/* Current execution centerpiece */}
      <section className="mt-6">
        <SectionTitle hint="the run that matters now">Current execution</SectionTitle>
        <CurrentExecution />
      </section>

      {/* Metrics + recent */}
      <section className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <SectionTitle>System metrics</SectionTitle>
          <div className="grid grid-cols-2 gap-3">
            <Metric label="Executions" value={data?.runs_total ?? 3} sub="all time" />
            <Metric label="Evidence" value={data?.metrics.evidence ?? 20} tone="accent" sub="minted" />
            <Metric label="Artifacts" value={data?.metrics.artifacts ?? 8} sub="produced" />
            <Metric label="Blocked" value={1} tone="block" sub="policy-denied" />
            <Metric label="Approvals" value={data?.pending_approvals ?? 1} tone="warn" sub="pending" />
            <Metric label="Tool failures" value={0} tone="ok" sub="last 24h" />
          </div>
        </div>

        <div className="lg:col-span-2">
          <SectionTitle hint="recent">Recent executions</SectionTitle>
          <RecentRuns loading={loading} />
        </div>
      </section>
    </div>
  );
}

function CurrentExecution() {
  const backend = useBackend();
  const { data } = useAsync(() => backend.getRun("run_9f3a2c71e0b4"), []);
  if (!data) return <div className="surface h-40 animate-pulse" />;
  const b = data;
  return (
    <Link href={`/runs/${b.run.id}`} className="block">
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        className="surface edge-live relative overflow-hidden px-6 py-5"
      >
        <div className="flex flex-wrap items-center gap-3">
          <RunStatusBadge status={b.run.status} />
          <span className="mono text-xs text-ink-3">{b.run.id}</span>
          <span className="text-xs text-ink-3">· {b.run.worker}</span>
        </div>
        <p className="mt-3 max-w-3xl text-[15px] leading-relaxed text-ink-0">{b.run.intent}</p>
        <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-ink-2">
          <span>
            <span className="text-ink-3">Phase </span>
            <span className="text-ink-0">Verify · score reproducibility</span>
          </span>
          <span>
            <span className="text-ink-3">Elapsed </span>
            <span className="text-ink-0">{fmtDuration(b.run.started, b.run.finished)}</span>
          </span>
          <span>
            <span className="text-ink-3">Evidence </span>
            <span className="text-accent">{b.run.evidence_count}</span>
          </span>
          <span>
            <span className="text-ink-3">Verification </span>
            <span className="text-ok">2 PASS</span>
          </span>
          <span>
            <span className="text-ink-3">Approvals </span>
            <span className="text-block">{b.run.approval_count} pending</span>
          </span>
        </div>
        <div className="pointer-events-none absolute right-5 top-5 flex items-center gap-1 text-xs text-ink-3">
          Open run <ArrowRight className="h-3.5 w-3.5" />
        </div>
      </motion.div>
    </Link>
  );
}

function RecentRuns({ loading }: { loading: boolean }) {
  const backend = useBackend();
  const { data } = useAsync(() => backend.listRuns(), []);
  if (loading) return <div className="space-y-2.5">{[0, 1, 2].map((i) => <div key={i} className="surface h-[88px] animate-pulse" />)}</div>;
  const runs = (data ?? []).slice(0, 4);
  return (
    <div className="space-y-2.5">
      {runs.map((r) => (
        <RunRow key={r.id} run={r} />
      ))}
    </div>
  );
}

function RunRow({ run }: { run: RunRecord }) {
  return (
    <Link href={`/runs/${run.id}`}>
      <div className="surface flex items-center gap-3 px-4 py-3 transition-colors hover:border-hairline">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <RunStatusBadge status={run.status} />
            <span className="mono text-[11px] text-ink-3">{run.id}</span>
          </div>
          <p className="mt-1 truncate text-sm text-ink-1">{run.intent}</p>
        </div>
        <div className="hidden w-32 justify-center sm:flex">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-3">
            <div
              className="h-full rounded-full bg-accent"
              style={{ width: `${Math.min(100, 40 + run.evidence_count * 4)}%` }}
            />
          </div>
        </div>
        <div className="hidden w-24 text-right text-xs text-ink-3 md:block">
          {fmtDuration(run.started, run.finished)}
        </div>
        <ArrowRight className="h-4 w-4 text-ink-3" />
      </div>
    </Link>
  );
}

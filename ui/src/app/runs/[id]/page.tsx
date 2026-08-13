"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { motion } from "framer-motion";
import { useBackend } from "@/components/providers/backend-provider";
import { useAsync } from "@/lib/use-async";
import { buildStageNodes, type StageNode } from "@/lib/run-graph";
import { ExecutionGraph, type GraphSelection } from "@/components/run/execution-graph";
import { Timeline } from "@/components/run/timeline";
import { StageDetail } from "@/components/run/stage-detail";
import {
  Badge,
  Hash,
  RunStatusBadge,
  SectionTitle,
} from "@/components/ui/primitives";
import { fmtDuration, fmtTime, STAGE_ORDER } from "@/lib/domain";
import { ArrowLeft, Rewind } from "lucide-react";
import type { RunBundle } from "@/lib/types";

export default function RunDetailPage() {
  const params = useParams<{ id: string }>();
  const backend = useBackend();
  const { data: run, loading } = useAsync(() => backend.getRun(params.id), [params.id]);

  if (loading) return <RunDetailSkeleton />;
  if (!run) return <RunNotFound id={params.id} />;

  return <RunDetail bundle={run} />;
}

function RunDetail({ bundle }: { bundle: RunBundle }) {
  const nodes = useMemo(() => buildStageNodes(bundle), [bundle]);
  const [sel, setSel] = useState<GraphSelection>({ key: "FINAL", refs: [bundle.run.id] });

  // signature interaction helper: when a claim/decision is opened elsewhere
  const focusKey = (k: string) => setSel({ key: k, refs: nodes.find((n) => n.key === k)?.refs ?? [] });

  return (
    <div className="mx-auto max-w-7xl px-5 py-5">
      <RunHeader bundle={bundle} />

      <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,360px)_minmax(0,1fr)]">
        {/* left: execution graph (the spine) */}
        <div>
          <SectionTitle hint="lifecycle">Execution</SectionTitle>
          <div className="surface p-3.5">
            <ExecutionGraph nodes={nodes} selected={sel.key} onSelect={setSel} />
          </div>
          <div className="mt-3">
            <Link
              href={`/replay/${encodeURIComponent(bundle.run.id)}`}
              className="flex w-full items-center justify-center gap-2 rounded-md border border-accent/30 bg-accent/10 px-3 py-2 text-sm font-medium text-accent transition-colors hover:bg-accent/15"
            >
              <Rewind className="h-4 w-4" /> Replay this run
            </Link>
          </div>
        </div>

        {/* right: stage detail + timeline */}
        <div className="space-y-5">
          <div>
            <SectionTitle hint="inspect">{sel.key} · details</SectionTitle>
            <StageDetail nodes={nodes} selection={sel} bundle={bundle} onFocusKey={focusKey} />
          </div>

          <div>
            <SectionTitle hint="chronological">Event timeline</SectionTitle>
            <div className="surface p-4">
              <Timeline events={bundle.timeline} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function RunHeader({ bundle }: { bundle: RunBundle }) {
  const r = bundle.run;
  return (
    <div className="surface relative overflow-hidden px-5 py-4">
      <div className="absolute right-0 top-0 h-28 w-60 bg-accent-glow blur-2xl" aria-hidden />
      <Link href="/runs" className="inline-flex items-center gap-1 text-xs text-ink-3 hover:text-ink-1">
        <ArrowLeft className="h-3.5 w-3.5" /> Runs
      </Link>
      <div className="relative mt-2 flex flex-wrap items-center gap-3">
        <RunStatusBadge status={r.status} />
        <Hash value={r.id} />
        <span className="text-xs text-ink-3">· seq #{r.seq}</span>
        <Badge tone="neutral">{r.worker}</Badge>
        <Badge tone="neutral">{r.procedure}</Badge>
      </div>
      <p className="relative mt-2 max-w-3xl text-[17px] leading-relaxed text-ink-0">{r.intent}</p>
      <div className="relative mt-3 flex flex-wrap items-center gap-x-6 gap-y-1.5 text-xs text-ink-2">
        <span>
          <span className="text-ink-3">Started </span>
          {fmtTime(r.started)}
        </span>
        <span>
          <span className="text-ink-3">Duration </span>
          {fmtDuration(r.started, r.finished)}
        </span>
        <span>
          <span className="text-ink-3">Evidence </span>
          <span className="text-accent">{r.evidence_count}</span>
        </span>
        <span>
          <span className="text-ink-3">Claims </span>
          {r.claim_count}
        </span>
        <span>
          <span className="text-ink-3">Approvals </span>
          <span className="text-block">{r.approval_count}</span>
        </span>
        <span>
          <span className="text-ink-3">Verifications </span>
          <span className="text-ok">{bundle.verifications.length} PASS</span>
        </span>
      </div>
      {r.summary ? (
        <p className="relative mt-3 border-t border-hairline-soft pt-3 text-sm text-ink-2">{r.summary}</p>
      ) : null}
    </div>
  );
}

function RunDetailSkeleton() {
  return (
    <div className="mx-auto max-w-7xl px-5 py-5">
      <div className="surface h-40 animate-pulse" />
      <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-[360px_1fr]">
        <div className="surface h-96 animate-pulse" />
        <div className="space-y-5">
          <div className="surface h-64 animate-pulse" />
          <div className="surface h-72 animate-pulse" />
        </div>
      </div>
    </div>
  );
}

function RunNotFound({ id }: { id: string }) {
  return (
    <div className="mx-auto max-w-3xl px-5 py-16">
      <div className="surface px-6 py-12 text-center">
        <div className="text-lg font-medium text-ink-0">Run not found</div>
        <p className="mt-2 text-sm text-ink-3">
          No execution with this id exists in the current backend.
        </p>
        <p className="mono mt-3 text-xs text-ink-4">{id}</p>
      </div>
    </div>
  );
}

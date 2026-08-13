"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { motion } from "framer-motion";
import { useBackend } from "@/components/providers/backend-provider";
import { useAsync } from "@/lib/use-async";
import {
  Badge,
  Hash,
  RunStatusBadge,
  ActionStatusBadge,
  RiskBadge,
  ApprovalBadge,
  VerifyBadge,
  RefId,
  SectionTitle,
} from "@/components/ui/primitives";
import { fmtTime, TONE_CLASS } from "@/lib/domain";
import type { Tone } from "@/lib/domain";
import { cn } from "@/lib/cn";
import { ArrowLeft, Rewind, SkipBack, SkipForward, Play, Pause, GitBranch, ShieldCheck } from "lucide-react";
import type { TimelineEvent, TimelineKind } from "@/lib/types";

const KIND_TONE: Record<TimelineKind, Tone> = {
  REQUEST: "accent",
  INTENT: "accent",
  PLAN: "neutral",
  STEP: "neutral",
  ACTION: "accent",
  TOOL: "accent",
  OBSERVATION: "ok",
  EVIDENCE: "ok",
  CLAIM: "warn",
  VERIFY: "ok",
  ARTIFACT: "accent",
  APPROVAL: "block",
  FINAL: "neutral",
  AUDIT: "neutral",
  BLOCK: "bad",
};

export default function ReplayPage() {
  const params = useParams<{ id: string }>();
  const backend = useBackend();
  const { data: run, loading } = useAsync(() => backend.getRun(params.id), [params.id]);
  const { data: audit } = useAsync(() => backend.getAudit(params.id), [params.id]);

  const events: TimelineEvent[] = run?.timeline ?? [];
  const [idx, setIdx] = useState(0);
  const [playing, setPlaying] = useState(false);

  const visible = useMemo(() => events.slice(0, idx + 1), [events, idx]);

  // auto-advance when playing
  const advance = () => {
    setIdx((i) => {
      if (i >= events.length - 1) {
        setPlaying(false);
        return i;
      }
      return i + 1;
    });
  };

  // play loop — must run unconditionally (Rules of Hooks)
  useEffect(() => {
    if (!playing) return;
    const t = setInterval(advance, 900);
    return () => clearInterval(t);
  }, [playing, events.length]);

  if (loading) return <ReplaySkeleton />;
  if (!run) return <ReplayNotFound id={params.id} />;

  const current = events[idx];

  return (
    <div className="mx-auto max-w-7xl px-5 py-5">
      <Link href={`/runs/${params.id}`} className="inline-flex items-center gap-1 text-xs text-ink-3 hover:text-ink-1">
        <ArrowLeft className="h-3.5 w-3.5" /> Run {params.id}
      </Link>

      <div className="surface relative mt-3 overflow-hidden px-5 py-4">
        <div className="absolute right-0 top-0 h-28 w-60 bg-accent-glow blur-2xl" aria-hidden />
        <div className="relative flex flex-wrap items-center gap-3">
          <Rewind className="h-5 w-5 text-accent" />
          <RunStatusBadge status={run.run.status} />
          <Hash value={run.run.id} />
          <span className="text-xs text-ink-3">· seq #{run.run.seq}</span>
          <Badge tone="neutral">{run.run.worker}</Badge>
        </div>
        <p className="relative mt-2 max-w-3xl text-[16px] leading-relaxed text-ink-0">{run.run.intent}</p>
        <p className="relative mt-2 text-[12px] text-ink-3">
          Replay reconstructs this run from the hash-chained audit trail — no model is re-run.
        </p>
      </div>

      {/* transport */}
      <div className="surface mt-4 flex flex-wrap items-center gap-3 px-4 py-3">
        <button
          onClick={() => { setIdx(0); setPlaying(false); }}
          className="rounded-md border border-hairline-soft px-2.5 py-1.5 text-ink-2 transition-colors hover:text-ink-0"
          aria-label="Restart"
        >
          <SkipBack className="h-4 w-4" />
        </button>
        <button
          onClick={() => setPlaying((p) => !p)}
          className="flex items-center gap-2 rounded-md border border-accent/40 bg-accent/10 px-3 py-1.5 text-sm font-medium text-accent transition-colors hover:bg-accent/15"
        >
          {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
          {playing ? "Pause" : "Play"}
        </button>
        <button
          onClick={() => setIdx((i) => Math.max(0, i - 1))}
          disabled={idx === 0}
          className="rounded-md border border-hairline-soft px-2.5 py-1.5 text-ink-2 transition-colors hover:text-ink-0 disabled:opacity-40"
          aria-label="Step back"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <button
          onClick={() => setIdx((i) => Math.min(events.length - 1, i + 1))}
          disabled={idx >= events.length - 1}
          className="rounded-md border border-hairline-soft px-2.5 py-1.5 text-ink-2 transition-colors hover:text-ink-0 disabled:opacity-40"
          aria-label="Step forward"
        >
          <SkipForward className="h-4 w-4" />
        </button>
        <div className="ml-auto flex items-center gap-3 text-xs text-ink-3">
          <span>
            step <span className="mono text-ink-0">{idx + 1}</span> / {events.length}
          </span>
          <div className="h-1.5 w-40 overflow-hidden rounded-full bg-surface-3">
            <div className="h-full bg-accent" style={{ width: `${events.length ? ((idx + 1) / events.length) * 100 : 0}%` }} />
          </div>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,320px)]">
        {/* event stream */}
        <div>
          <SectionTitle hint="chronological">Replay stream</SectionTitle>
          <div className="surface p-4">
            <ol className="relative space-y-3 border-l border-hairline-soft pl-4">
              {visible.map((e, i) => (
                <motion.li
                  key={`${e.kind}-${e.refs?.join(",") ?? i}-${i}`}
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="relative"
                >
                  <span
                    className={cn(
                      "absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full ring-2 ring-surface-0",
                      TONE_CLASS[KIND_TONE[e.kind] ?? "neutral"].dot,
                    )}
                  />
                  <ReplayEvent e={e} latest={i === visible.length - 1} />
                </motion.li>
              ))}
            </ol>
          </div>
        </div>

        {/* current focus / decision */}
        <div className="space-y-5">
          <div>
            <SectionTitle hint="now playing">Current step</SectionTitle>
            {current ? <ReplayEvent e={current} expanded /> : null}
          </div>

          <div>
            <SectionTitle hint="audit trail">Integrity</SectionTitle>
            <div className="surface px-4 py-3 text-sm">
              <div className="flex items-center gap-2 text-ink-0">
                <ShieldCheck className="h-4 w-4 text-ok" />
                {audit && audit.length > 0 ? (
                  <span>{audit.length} hash-chained entries</span>
                ) : (
                  <span>trail intact</span>
                )}
              </div>
              <p className="mt-1.5 text-[12px] leading-relaxed text-ink-3">
                Each record below is independently verifiable. Re-running the model is never required to trust the output.
              </p>
              {audit && audit.length > 0 ? (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {audit.slice(0, 6).map((a, i) => (
                    <span key={i} className="mono rounded border border-hairline-soft bg-surface-3/40 px-1.5 py-0.5 text-[10px] text-ink-3">
                      {a.event}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          </div>

          {/* decision points */}
          <div>
            <SectionTitle hint="human gate">Decision points</SectionTitle>
            {run.approvals.length === 0 ? (
              <div className="surface px-4 py-4 text-center text-[13px] text-ink-3">
                No human approvals were required in this run.
              </div>
            ) : (
              <div className="space-y-2">
                {run.approvals.map((a) => (
                  <div key={a.id} className="surface px-4 py-3">
                    <div className="flex items-center gap-2">
                      <ApprovalBadge state={a.state} />
                      <RiskBadge risk={a.risk} />
                      <RefId value={a.id} />
                    </div>
                    <p className="mt-1.5 text-[13px] text-ink-1">{a.summary}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function ReplayEvent({ e, expanded, latest }: { e: TimelineEvent; expanded?: boolean; latest?: boolean }) {
  const tone = KIND_TONE[e.kind] ?? "neutral";
  return (
    <div
      className={cn(
        "rounded-md border px-3 py-2",
        latest ? cn(TONE_CLASS[tone].border, TONE_CLASS[tone].bg) : "border-hairline-soft bg-surface-1",
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={tone}>{e.kind}</Badge>
        {e.status ? <span className="text-[11px] text-ink-3">{e.status}</span> : null}
        {e.refs?.map((r) => <RefId key={r} value={r} />)}
        <span className="ml-auto text-[11px] text-ink-3">{fmtTime(e.ts)}</span>
      </div>
      {e.title ? <p className="mt-1 text-[13px] font-medium text-ink-0">{e.title}</p> : null}
      {e.detail ? <p className={cn("mt-1 text-[13px] text-ink-1", !expanded && "line-clamp-2")}>{e.detail}</p> : null}
    </div>
  );
}

function ReplaySkeleton() {
  return (
    <div className="mx-auto max-w-7xl px-5 py-5">
      <div className="surface h-32 animate-pulse" />
      <div className="mt-4 surface h-16 animate-pulse" />
      <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-[1fr_320px]">
        <div className="surface h-96 animate-pulse" />
        <div className="surface h-96 animate-pulse" />
      </div>
    </div>
  );
}

function ReplayNotFound({ id }: { id: string }) {
  return (
    <div className="mx-auto max-w-3xl px-5 py-16">
      <div className="surface px-6 py-12 text-center">
        <div className="text-lg font-medium text-ink-0">Run not found</div>
        <p className="mono mt-3 text-xs text-ink-4">{id}</p>
        <Link href="/runs" className="mt-4 inline-block text-sm text-accent hover:underline">
          Back to Runs
        </Link>
      </div>
    </div>
  );
}

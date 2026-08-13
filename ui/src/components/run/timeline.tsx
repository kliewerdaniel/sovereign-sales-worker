"use client";

import { cn } from "@/lib/cn";
import { TONE_CLASS } from "@/lib/domain";
import { fmtTime } from "@/lib/domain";
import type { TimelineEvent, TimelineKind } from "@/lib/types";

const KIND_TONE: Record<TimelineKind, keyof typeof TONE_CLASS> = {
  REQUEST: "accent",
  INTENT: "neutral",
  PLAN: "neutral",
  STEP: "neutral",
  ACTION: "accent",
  TOOL: "accent",
  OBSERVATION: "ok",
  EVIDENCE: "accent",
  CLAIM: "ok",
  VERIFY: "ok",
  ARTIFACT: "accent",
  APPROVAL: "block",
  FINAL: "warn",
  AUDIT: "neutral",
  BLOCK: "block",
};

const KIND_LABEL: Record<TimelineKind, string> = {
  REQUEST: "REQUEST",
  INTENT: "INTENT",
  PLAN: "PLAN",
  STEP: "STEP",
  ACTION: "ACTION",
  TOOL: "TOOL",
  OBSERVATION: "OBSERVATION",
  EVIDENCE: "EVIDENCE",
  CLAIM: "CLAIM",
  VERIFY: "VERIFY",
  ARTIFACT: "ARTIFACT",
  APPROVAL: "APPROVAL",
  FINAL: "FINAL",
  AUDIT: "AUDIT",
  BLOCK: "BLOCK",
};

export function Timeline({ events }: { events: TimelineEvent[] }) {
  return (
    <ol className="relative">
      {events.map((e, i) => {
        const tone = TONE_CLASS[KIND_TONE[e.kind]];
        const statTone = e.status ? TONE_CLASS[e.status === "ok" ? "ok" : e.status === "blocked" ? "block" : e.status === "pending" ? "block" : "warn"] : null;
        return (
          <li key={i} className="flex gap-3 pb-3 last:pb-0">
            <div className="flex w-16 shrink-0 flex-col items-end pt-0.5">
              <span className="mono text-[10px] text-ink-4">{fmtTime(e.ts)}</span>
            </div>
            <div className="relative flex flex-col items-center">
              <span className={cn("mt-1 h-2 w-2 rounded-full", tone.dot)} />
              {i < events.length - 1 ? (
                <span className="mt-0.5 w-px flex-1 bg-hairline-soft" aria-hidden />
              ) : null}
            </div>
            <div className="min-w-0 flex-1 pb-1">
              <div className="flex items-center gap-2">
                <span className={cn("mono text-[10px] font-semibold tracking-wider", tone.text)}>
                  {KIND_LABEL[e.kind]}
                </span>
                {statTone ? (
                  <span className={cn("rounded-full border px-1.5 py-0.5 text-[9px]", statTone.text, statTone.border)}>
                    {e.status}
                  </span>
                ) : null}
              </div>
              <div className="mt-0.5 text-sm text-ink-1">{e.title}</div>
              {e.detail ? <div className="mt-0.5 text-xs text-ink-3">{e.detail}</div> : null}
              {e.refs && e.refs.length ? (
                <div className="mt-1 flex flex-wrap gap-1">
                  {e.refs.map((r) => (
                    <span key={r} className="mono rounded border border-hairline-soft bg-surface-3/50 px-1.5 py-0.5 text-[10px] text-ink-3">
                      {r}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

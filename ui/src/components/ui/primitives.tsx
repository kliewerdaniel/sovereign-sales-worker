"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/cn";
import {
  APPROVAL_TONE,
  CONFIDENCE_TONE,
  OUTREACH_TONE,
  PROVENANCE_LABEL,
  PROVENANCE_TONE,
  RISK_LABEL,
  RISK_TONE,
  RUN_LABEL,
  TONE_CLASS,
  Tone,
  VERIFY_TONE,
  actionTone,
  runTone,
  stepTone,
} from "@/lib/domain";
import type {
  ActionStatus,
  ApprovalState,
  ClaimTier,
  Confidence,
  OutreachState,
  PipelineStage,
  Provenance,
  RiskLevel,
  RunStatus,
  StepStatus,
  VerificationOutcome,
} from "@/lib/types";

export function StatusDot({ tone, pulse }: { tone: Tone; pulse?: boolean }) {
  const c = TONE_CLASS[tone];
  return (
    <span
      className={cn("inline-block h-2 w-2 rounded-full", c.dot, pulse && tone === "accent" ? "live-dot" : "")}
      aria-hidden
    />
  );
}

export function Badge({
  tone = "neutral",
  children,
  className,
  title,
}: {
  tone?: Tone;
  children: React.ReactNode;
  className?: string;
  title?: string;
}) {
  const c = TONE_CLASS[tone];
  return (
    <span
      title={title}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium leading-none",
        c.text,
        c.bg,
        c.border,
        className,
      )}
    >
      {children}
    </span>
  );
}

export function RunStatusBadge({ status }: { status: RunStatus }) {
  const tone = runTone(status);
  return (
    <Badge tone={tone}>
      <StatusDot tone={tone} pulse={status === "EXECUTING" || status === "RUNNING" || status === "AWAITING_APPROVAL"} />
      {RUN_LABEL[status]}
    </Badge>
  );
}

export function ActionStatusBadge({ status }: { status: ActionStatus }) {
  return <Badge tone={actionTone(status)}>{status}</Badge>;
}

export function StepStatusBadge({ status }: { status: StepStatus }) {
  return <Badge tone={stepTone(status)}>{status}</Badge>;
}

export function VerifyBadge({ outcome }: { outcome: VerificationOutcome }) {
  return <Badge tone={VERIFY_TONE[outcome]}>{outcome}</Badge>;
}

export function ApprovalBadge({ state }: { state: ApprovalState }) {
  return <Badge tone={APPROVAL_TONE[state]}>{state}</Badge>;
}

export function RiskBadge({ risk }: { risk: RiskLevel }) {
  return (
    <Badge tone={RISK_TONE[risk]} title={`Risk level: ${RISK_LABEL[risk]}`}>
      {RISK_LABEL[risk]}
    </Badge>
  );
}

export function ProvenanceBadge({ p }: { p: Provenance }) {
  return <Badge tone={PROVENANCE_TONE[p]}>{PROVENANCE_LABEL[p]}</Badge>;
}

export function ConfidenceBadge({ c }: { c: Confidence }) {
  return <Badge tone={CONFIDENCE_TONE[c]}>{c}</Badge>;
}

export function OutreachBadge({ s }: { s: OutreachState }) {
  return <Badge tone={OUTREACH_TONE[s]}>{s}</Badge>;
}

export function TierBadge({ tier }: { tier: ClaimTier }) {
  return <Badge tone={tier === "OBSERVED" || tier === "CLIENT_VERIFIED" || tier === "CASE_STUDY" ? "ok" : tier === "HYPOTHESIS" ? "warn" : "neutral"}>{tier}</Badge>;
}

// Monospace reference chip with copy-to-clipboard + brief highlight.
export function RefId({ value, className }: { value: string; className?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard?.writeText(value);
        setCopied(true);
        setTimeout(() => setCopied(false), 900);
      }}
      className={cn(
        "mono rounded border border-hairline-soft bg-surface-3/50 px-1.5 py-0.5 text-[11px] text-ink-2 transition-colors hover:text-accent",
        copied && "border-accent/40 bg-accent/10 text-accent",
        className,
      )}
      title={`Copy ${value}`}
      aria-label={`Copy identifier ${value}`}
    >
      {copied ? "copied" : value}
    </button>
  );
}

// Animated hash reveal — used for evidence/artifact hashes.
export function Hash({ value }: { value: string }) {
  return (
    <motion.span
      initial={{ opacity: 0.4 }}
      animate={{ opacity: 1 }}
      className="mono text-[11px] text-ink-3"
      title={value}
    >
      {value}
    </motion.span>
  );
}

export function Card({
  children,
  className,
  onClick,
  interactive,
}: {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
  interactive?: boolean;
}) {
  return (
    <div
      onClick={onClick}
      className={cn(
        "surface p-4",
        interactive && "cursor-pointer transition-colors hover:border-hairline",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function SectionTitle({ children, hint }: { children: React.ReactNode; hint?: string }) {
  return (
    <div className="mb-3 flex items-baseline justify-between">
      <h2 className="text-sm font-semibold tracking-wide text-ink-1">{children}</h2>
      {hint ? <span className="text-xs text-ink-3">{hint}</span> : null}
    </div>
  );
}

export function EmptyState({
  title,
  body,
  action,
  icon,
}: {
  title: string;
  body: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
}) {
  return (
    <div className="surface flex flex-col items-center justify-center gap-3 px-6 py-14 text-center">
      {icon ? <div className="text-ink-3">{icon}</div> : null}
      <div className="text-base font-medium text-ink-1">{title}</div>
      <p className="max-w-md text-sm leading-relaxed text-ink-3">{body}</p>
      {action ?? null}
    </div>
  );
}

export function Metric({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  tone?: Tone;
}) {
  return (
    <div className="surface px-3.5 py-3">
      <div className="text-[11px] uppercase tracking-wider text-ink-3">{label}</div>
      <div className={cn("mt-1 text-2xl font-semibold tabular-nums", tone ? TONE_CLASS[tone].text : "text-ink-0")}>
        {value}
      </div>
      {sub ? <div className="mt-0.5 text-xs text-ink-3">{sub}</div> : null}
    </div>
  );
}

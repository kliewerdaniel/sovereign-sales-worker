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
} from "./types";

/**
 * Central semantic-color + label mapping. Every status the runtime can emit is
 * represented here so the whole UI speaks one visual language. Colors reference
 * the CSS variables defined in globals.css. "tone" drives text/border/bg hues.
 */

export type Tone =
  | "neutral"
  | "accent"
  | "ok"
  | "warn"
  | "bad"
  | "block"
  | "unknown";

export function runTone(s: RunStatus): Tone {
  switch (s) {
    case "SUCCESS":
      return "ok";
    case "PARTIAL_SUCCESS":
      return "warn";
    case "FAILED":
    case "BLOCKED":
    case "INSUFFICIENT_EVIDENCE":
    case "DENIED":
    case "CANCELLED":
      return "bad";
    case "AWAITING_APPROVAL":
      return "block";
    case "EXECUTING":
    case "RUNNING":
    case "VERIFYING":
      return "accent";
    default:
      return "neutral";
  }
}

export const RUN_LABEL: Record<RunStatus, string> = {
  PENDING: "Pending",
  PLANNING: "Planning",
  RUNNING: "Running",
  EXECUTING: "Executing",
  AWAITING_APPROVAL: "Awaiting approval",
  VERIFYING: "Verifying",
  SUCCESS: "Success",
  PARTIAL_SUCCESS: "Partial success",
  FAILED: "Failed",
  BLOCKED: "Blocked",
  INSUFFICIENT_EVIDENCE: "Insufficient evidence",
  CANCELLED: "Cancelled",
  DENIED: "Denied",
};

export function actionTone(s: ActionStatus): Tone {
  switch (s) {
    case "EXECUTED":
      return "ok";
    case "APPROVED":
      return "ok";
    case "EXECUTING":
      return "accent";
    case "PROPOSED":
    case "AWAITING_APPROVAL":
      return "block";
    case "REJECTED":
    case "DENIED":
    case "FAILED":
      return "bad";
    case "SKIPPED":
      return "neutral";
    default:
      return "neutral";
  }
}

export function stepTone(s: StepStatus): Tone {
  switch (s) {
    case "DONE":
      return "ok";
    case "RUNNING":
      return "accent";
    case "FAILED":
      return "bad";
    case "BLOCKED":
    case "AWAITING_APPROVAL":
      return "block";
    case "SKIPPED":
      return "neutral";
    default:
      return "neutral";
  }
}

export const VERIFY_TONE: Record<VerificationOutcome, Tone> = {
  PASS: "ok",
  FAIL: "bad",
  UNVERIFIABLE: "warn",
};

export const APPROVAL_TONE: Record<ApprovalState, Tone> = {
  PENDING: "block",
  APPROVED: "ok",
  REJECTED: "bad",
  EXPIRED: "warn",
};

export const RISK_TONE: Record<RiskLevel, Tone> = {
  read: "neutral",
  reversible: "accent",
  external: "warn",
  financial: "warn",
  destructive: "bad",
};

export const RISK_LABEL: Record<RiskLevel, string> = {
  read: "Read",
  reversible: "Reversible",
  external: "External",
  financial: "Financial",
  destructive: "Destructive",
};

export const PROVENANCE_TONE: Record<Provenance, Tone> = {
  known: "neutral",
  retrieved: "accent",
  observed: "ok",
  inferred: "warn",
  hypothesized: "warn",
  verified: "ok",
};

export const PROVENANCE_LABEL: Record<Provenance, string> = {
  known: "Known",
  retrieved: "Retrieved",
  observed: "Observed",
  inferred: "Inferred",
  hypothesized: "Hypothesized",
  verified: "Verified",
};

export const TIER_TONE: Record<ClaimTier, Tone> = {
  CLAIM: "neutral",
  HYPOTHESIS: "warn",
  OBSERVED: "ok",
  VERIFIED: "ok",
  CLIENT_VERIFIED: "ok",
  CASE_STUDY: "accent",
};

export const CONFIDENCE_TONE: Record<Confidence, Tone> = {
  HIGH: "ok",
  MEDIUM: "warn",
  LOW: "bad",
  UNKNOWN: "neutral",
};

export const OUTREACH_TONE: Record<OutreachState, Tone> = {
  draft: "neutral",
  approved: "accent",
  sent: "ok",
  rejected: "bad",
};

export const OUTREACH_LABEL: Record<OutreachState, string> = {
  draft: "Draft",
  approved: "Approved",
  sent: "Sent",
  rejected: "Rejected",
};

export const STAGE_LABEL: Record<PipelineStage, string> = {
  prospect: "Prospect",
  contacted: "Contacted",
  responded: "Responded",
  discovery_scheduled: "Discovery scheduled",
  discovery_completed: "Discovery completed",
  qualified: "Qualified",
  audit_in_progress: "Audit in progress",
  proposal_sent: "Proposal sent",
  negotiation: "Negotiation",
  won: "Won",
  lost: "Lost",
  onboarding: "Onboarding",
  implementation: "Implementation",
  completed: "Completed",
  expansion: "Expansion",
};

export const STAGE_ORDER: PipelineStage[] = [
  "prospect",
  "contacted",
  "responded",
  "discovery_scheduled",
  "discovery_completed",
  "qualified",
  "audit_in_progress",
  "proposal_sent",
  "negotiation",
  "won",
  "lost",
];

export const TONE_CLASS: Record<Tone, { text: string; bg: string; border: string; dot: string }> = {
  neutral: {
    text: "text-ink-2",
    bg: "bg-surface-3/60",
    border: "border-hairline",
    dot: "bg-ink-3",
  },
  accent: {
    text: "text-accent",
    bg: "bg-accent/10",
    border: "border-accent/30",
    dot: "bg-accent",
  },
  ok: {
    text: "text-ok",
    bg: "bg-ok/10",
    border: "border-ok/30",
    dot: "bg-ok",
  },
  warn: {
    text: "text-warn",
    bg: "bg-warn/10",
    border: "border-warn/30",
    dot: "bg-warn",
  },
  bad: {
    text: "text-bad",
    bg: "bg-bad/10",
    border: "border-bad/30",
    dot: "bg-bad",
  },
  block: {
    text: "text-block",
    bg: "bg-block/10",
    border: "border-block/30",
    dot: "bg-block",
  },
  unknown: {
    text: "text-ink-3",
    bg: "bg-surface-3/40",
    border: "border-hairline",
    dot: "bg-ink-4",
  },
};

export function toneOf(kind: string): Tone {
  return (kind as Tone) in TONE_CLASS ? (kind as Tone) : "neutral";
}

/** deterministic short hash for monospace ids (visual only) */
export function shortId(id: string, head = 8): string {
  if (!id) return "";
  const clean = id.replace(/^[\w]+_/, "");
  return clean.slice(0, head);
}

export function fmtTime(ts: number): string {
  if (!ts) return "—";
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function fmtDate(ts: number): string {
  if (!ts) return "—";
  const d = new Date(ts * 1000);
  return d.toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" });
}

export function fmtDuration(started: number, finished: number): string {
  if (!started) return "—";
  // An unfinished run (finished === 0) is still in progress — don't compute a
  // wall-clock elapsed against Date.now(), which would grow forever and look
  // absurd (e.g. "10168h"). Show it as in progress instead.
  if (!finished) return "in progress";
  const s = Math.max(0, Math.round(finished - started));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  if (m < 60) return `${m}m ${rem}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

export function fmtBytes(n: number): string {
  if (!n) return "0 B";
  const u = ["B", "KB", "MB", "GB"];
  let i = 0;
  let x = n;
  while (x >= 1024 && i < u.length - 1) {
    x /= 1024;
    i++;
  }
  return `${x.toFixed(x < 10 && i > 0 ? 1 : 0)} ${u[i]}`;
}

export function pct(n: number): string {
  return `${Math.round(n)}%`;
}

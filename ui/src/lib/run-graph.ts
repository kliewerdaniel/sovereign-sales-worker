import type { RunBundle, TimelineKind } from "./types";
import { actionTone, APPROVAL_TONE, runTone, Tone, VERIFY_TONE } from "./domain";

export interface StageNode {
  key: TimelineKind;
  label: string;
  status: Tone;
  statusLabel: string;
  detail: string;
  /** ids of run records attached to this stage, for the detail panel */
  refs: string[];
  /** short count badge, if meaningful */
  count?: number;
}

const LABELS: Record<string, string> = {
  REQUEST: "Request",
  INTENT: "Intent",
  PLAN: "Plan",
  ACTION: "Action",
  TOOL: "Tool",
  OBSERVATION: "Observation",
  EVIDENCE: "Evidence",
  CLAIM: "Claim",
  VERIFY: "Verification",
  ARTIFACT: "Artifact",
  APPROVAL: "Approval",
  FINAL: "Final",
  AUDIT: "Audit",
  BLOCK: "Block",
};

/** Derive the 12-stage lifecycle spine (REQUEST → … → AUDIT) from a run,
 *  mapping real run records onto each stage with an honest status. */
export function buildStageNodes(b: RunBundle): StageNode[] {
  const r = b.run;
  const plan = b.plan ?? { id: "", step_ids: [] as string[], rationale: "no plan" };
  const anyBlocked = b.actions.some((a) => a.status === "DENIED" || a.status === "REJECTED");
  const anyPending = b.approvals.some((a) => a.state === "PENDING");

  const actionToneAgg = ((): Tone => {
    if (b.actions.every((a) => a.status === "EXECUTED" || a.status === "APPROVED")) return "ok";
    if (b.actions.some((a) => a.status === "DENIED" || a.status === "REJECTED")) return "block";
    return "warn";
  })();

  return [
    {
      key: "REQUEST",
      label: LABELS.REQUEST,
      status: "neutral",
      statusLabel: "received",
      detail: b.task.request,
      refs: [b.task.id],
      count: 1,
    },
    {
      key: "INTENT",
      label: LABELS.INTENT,
      status: "neutral",
      statusLabel: "resolved",
      detail: b.task.intent,
      refs: [b.task.id],
    },
    {
      key: "PLAN",
      label: LABELS.PLAN,
      status: "ok",
      statusLabel: "created",
      detail: `${plan.step_ids.length} steps · ${plan.rationale}`,
      refs: [plan.id, ...plan.step_ids],
      count: plan.step_ids.length,
    },
    {
      key: "ACTION",
      label: LABELS.ACTION,
      status: actionToneAgg,
      statusLabel: actionToneAgg === "ok" ? "executed" : actionToneAgg === "block" ? "1 denied" : "partial",
      detail: `${b.actions.length} actions proposed`,
      refs: b.actions.map((a) => a.id),
      count: b.actions.length,
    },
    {
      key: "TOOL",
      label: LABELS.TOOL,
      status: anyBlocked ? "block" : "ok",
      statusLabel: anyBlocked ? "1 blocked" : "called",
      detail: b.actions.map((a) => a.tool).join(" · "),
      refs: b.actions.map((a) => a.id),
    },
    {
      key: "OBSERVATION",
      label: LABELS.OBSERVATION,
      status: b.observations.length ? "ok" : "neutral",
      statusLabel: b.observations.length ? "recorded" : "none",
      detail: `${b.observations.length} observations from tool calls`,
      refs: b.observations.map((o) => o.id),
      count: b.observations.length,
    },
    {
      key: "EVIDENCE",
      label: LABELS.EVIDENCE,
      status: b.evidence.length ? "accent" : "neutral",
      statusLabel: b.evidence.length ? "minted" : "none",
      detail: `${b.evidence.length} evidence records with source references`,
      refs: b.evidence.map((e) => e.id),
      count: b.evidence.length,
    },
    {
      key: "CLAIM",
      label: LABELS.CLAIM,
      status: b.claims.length ? "ok" : "neutral",
      statusLabel: b.claims.length ? "asserted" : "none",
      detail: `${b.claims.length} claims`,
      refs: b.claims.map((c) => c.id),
      count: b.claims.length,
    },
    {
      key: "VERIFY",
      label: LABELS.VERIFY,
      status: b.verifications.length ? VERIFY_TONE[b.verifications[0].outcome] : "neutral",
      statusLabel: b.verifications.length
        ? `${b.verifications.filter((v) => v.outcome === "PASS").length} pass`
        : "none",
      detail: `${b.verifications.length} verification checks`,
      refs: b.verifications.map((v) => v.id),
      count: b.verifications.length,
    },
    {
      key: "ARTIFACT",
      label: LABELS.ARTIFACT,
      status: b.artifacts.length ? "accent" : "neutral",
      statusLabel: b.artifacts.length ? "produced" : "none",
      detail: `${b.artifacts.length} artifacts`,
      refs: b.artifacts.map((a) => a.id),
      count: b.artifacts.length,
    },
    {
      key: "APPROVAL",
      label: LABELS.APPROVAL,
      status: anyPending ? "block" : b.approvals.length ? APPROVAL_TONE[b.approvals[0].state] : "neutral",
      statusLabel: anyPending ? "pending" : b.approvals.length ? "closed" : "none",
      detail: `${b.approvals.length} approval requests`,
      refs: b.approvals.map((a) => a.id),
      count: b.approvals.length,
    },
    {
      key: "FINAL",
      label: LABELS.FINAL,
      status: runTone(r.status),
      statusLabel: r.status,
      detail: r.summary,
      refs: [r.id],
    },
    {
      key: "AUDIT",
      label: LABELS.AUDIT,
      status: "ok",
      statusLabel: "chained",
      detail: `${b.audit.length} hash-chained audit entries`,
      refs: b.audit.map((a) => a.id),
      count: b.audit.length,
    },
  ];
}

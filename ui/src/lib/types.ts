/**
 * Sovereign Worker — domain types.
 *
 * These mirror the Python runtime's persisted records (sworker/models.py,
 * sworker/sales/models.py) and the /api/v1 JSON contract. The UI never
 * invents fields the backend doesn't have. Demo data conforms to these shapes.
 */

// ---------------------------------------------------------------------------
// Enums (exact vocab from sworker/models.py)
// ---------------------------------------------------------------------------

export type RiskLevel =
  | "read"
  | "reversible"
  | "external"
  | "financial"
  | "destructive";

export const RISK_ORDER: RiskLevel[] = [
  "read",
  "reversible",
  "external",
  "financial",
  "destructive",
];

export type RunStatus =
  | "PENDING"
  | "PLANNING"
  | "RUNNING"
  | "EXECUTING"
  | "AWAITING_APPROVAL"
  | "VERIFYING"
  | "SUCCESS"
  | "PARTIAL_SUCCESS"
  | "FAILED"
  | "BLOCKED"
  | "INSUFFICIENT_EVIDENCE"
  | "CANCELLED"
  | "DENIED";

export type ActionStatus =
  | "PROPOSED"
  | "AWAITING_APPROVAL"
  | "APPROVED"
  | "REJECTED"
  | "DENIED"
  | "EXECUTING"
  | "EXECUTED"
  | "FAILED"
  | "SKIPPED";

export type StepStatus =
  | "PENDING"
  | "RUNNING"
  | "DONE"
  | "FAILED"
  | "BLOCKED"
  | "AWAITING_APPROVAL"
  | "SKIPPED";

/** How the worker came to hold something. Never collapsed. */
export type Provenance =
  | "known" // in worker instructions/config
  | "retrieved" // from compiled company knowledge
  | "observed" // returned by a tool
  | "inferred" // derived deterministically from other evidence
  | "hypothesized" // model-generated, unverified
  | "verified"; // deterministically re-checked

export type Confidence = "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN";

export type VerificationOutcome = "PASS" | "FAIL" | "UNVERIFIABLE";

export type ApprovalState = "PENDING" | "APPROVED" | "REJECTED" | "EXPIRED";

// Sales claim tiers (sworker/sales/models.py)
export type ClaimTier =
  | "CLAIM"
  | "HYPOTHESIS"
  | "OBSERVED"
  | "VERIFIED"
  | "CLIENT_VERIFIED"
  | "CASE_STUDY";

export const CLAIM_TIER_ORDER: ClaimTier[] = [
  "CLAIM",
  "HYPOTHESIS",
  "OBSERVED",
  "CLIENT_VERIFIED",
  "CASE_STUDY",
];

export type OutreachState = "draft" | "approved" | "sent" | "rejected";

export type PipelineStage =
  | "prospect"
  | "contacted"
  | "responded"
  | "discovery_scheduled"
  | "discovery_completed"
  | "qualified"
  | "audit_in_progress"
  | "proposal_sent"
  | "negotiation"
  | "won"
  | "lost"
  | "onboarding"
  | "implementation"
  | "completed"
  | "expansion";

// ---------------------------------------------------------------------------
// Execution lifecycle records
// ---------------------------------------------------------------------------

export interface TaskRecord {
  id: string;
  request: string;
  worker: string;
  intent: string;
  created: number;
  origin: "cli" | "schedule" | "api";
  trigger: "manual" | "schedule" | "api";
  procedure: string;
  inputs: Record<string, unknown>;
}

export interface PlanRecord {
  id: string;
  run_id: string;
  task_id: string;
  intent: string;
  rationale: string;
  step_ids: string[];
  created: number;
  source: "model" | "procedure" | "fallback";
}

export interface StepRecord {
  id: string;
  run_id: string;
  plan_id: string;
  index: number;
  description: string;
  tool: string;
  args: Record<string, unknown>;
  status: StepStatus;
  note: string;
  observation_id: string;
  detail: string;
}

export interface ActionRecord {
  id: string;
  run_id: string;
  step_id: string;
  tool: string;
  args: Record<string, unknown>;
  risk: RiskLevel;
  status: ActionStatus;
  summary: string;
  rationale: string;
  reason: string;
  reversible: boolean;
  approval_id: string;
  observation_id: string;
  created: number;
  executed: number;
  attempt: number;
}

export interface ObservationRecord {
  id: string;
  run_id: string;
  action_id: string;
  ok: boolean;
  output: string;
  error: string;
  data: Record<string, unknown>;
  truncated: boolean;
  duration_ms: number;
  /** Fired injection rule name if the ingested content was flagged. */
  injection: string;
  created: number;
}

export interface EvidenceRecord {
  id: string;
  run_id: string;
  provenance: Provenance;
  summary: string;
  source_ref: string; // file path, atlas claim id, url, tool name
  observation_id: string;
  excerpt: string;
  created: number;
}

export interface ClaimRecord {
  id: string;
  run_id: string;
  text: string;
  provenance: ClaimTier;
  confidence: Confidence;
  evidence_ids: string[];
  verification_ids: string[];
  refuted: boolean;
  created: number;
}

export interface VerificationRecord {
  id: string;
  run_id: string;
  claim_id: string;
  check: string;
  outcome: VerificationOutcome;
  detail: string;
  expected: string;
  actual: string;
  created: number;
}

export interface ApprovalRecord {
  id: string;
  run_id: string;
  action_id: string;
  risk: RiskLevel;
  summary: string;
  state: ApprovalState;
  reason: string;
  evidence_ids: string[];
  decided_by: string;
  decided_at: number;
  note: string;
  created: number;
  quorum: number;
  min_role: string;
  votes: Array<{ state: string; by: string; role: string; note: string; at: number }>;
  escalations: number;
}

export type ArtifactKind =
  | "markdown"
  | "csv"
  | "json"
  | "png"
  | "code"
  | "message"
  | "report"
  | "list"
  | "decision";

export interface ArtifactRecord {
  id: string;
  run_id: string;
  path: string;
  kind: ArtifactKind;
  title: string;
  description: string;
  bytes: number;
  sha256: string;
  claim_ids: string[];
  created: number;
  /** content is provided by the adapter for preview (demo) or fetched live. */
  content?: string;
}

export interface RunRecord {
  id: string;
  task_id: string;
  worker: string;
  status: RunStatus;
  plan_id: string;
  intent: string;
  trigger: "manual" | "schedule" | "api";
  procedure: string;
  started: number;
  finished: number;
  summary: string;
  error: string;
  evidence_count: number;
  claim_count: number;
  approval_count: number;
  artifact_ids: string[];
  verifications: unknown[];
  seq: number;
  degradations: string[];
}

// ---------------------------------------------------------------------------
// Timeline / inspect event (sworker inspect /api/v1/inspect)
// ---------------------------------------------------------------------------

export type TimelineKind =
  | "REQUEST"
  | "INTENT"
  | "PLAN"
  | "STEP"
  | "ACTION"
  | "TOOL"
  | "OBSERVATION"
  | "EVIDENCE"
  | "CLAIM"
  | "VERIFY"
  | "ARTIFACT"
  | "APPROVAL"
  | "FINAL"
  | "AUDIT"
  | "BLOCK";

export interface TimelineEvent {
  ts: number;
  kind: TimelineKind;
  title: string;
  detail?: string;
  /** ids this event links to (evidence/action/artifact) */
  refs?: string[];
  status?: "ok" | "fail" | "warn" | "pending" | "blocked";
}

// ---------------------------------------------------------------------------
// Worker definition / policy (sworker/config.py)
// ---------------------------------------------------------------------------

export type PolicyValue = "auto" | "approve" | "deny";

export interface WorkerConfig {
  name: string;
  role: string;
  instructions: string;
  knowledge: string[];
  tools: string[];
  procedures: string[];
  connectors: Array<Record<string, unknown>>;
  policy: Record<RiskLevel, PolicyValue>;
  fs_roots: string[];
  shell_allow: string[];
  env_allow: string[];
  max_steps: number;
  max_runtime: number;
  max_actions: number;
  max_tool_calls: number;
  max_artifact_bytes: number;
  browser_allow: string[];
  message_allow: string[];
  sandbox: "none" | "docker";
  egress_allow: string[];
  dlp_rules: string[];
  disabled: boolean;
  triggers: Array<Record<string, unknown>>;
  approval_policy: Record<string, { quorum: number; min_role: string }>;
  path: string;
}

// ---------------------------------------------------------------------------
// Tool registry (sworker/tools/base.py Tool.spec)
// ---------------------------------------------------------------------------

export interface ToolSpec {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  risk_level: RiskLevel;
  permissions: string[];
  reversible: boolean;
  requires_approval: boolean;
  categories: string[];
  /** adapter-supplied telemetry (not in backend spec, but derivable) */
  calls?: number;
  failures?: number;
  evidence?: number;
  last_used?: number;
}

// ---------------------------------------------------------------------------
// Sales domain (sworker/sales/models.py) — full projection
// ---------------------------------------------------------------------------

export interface SalesCompany {
  id: string;
  name: string;
  domain: string;
  industry: string;
  geography: string;
  team_size: number;
  description: string;
  website: string;
  source: string;
  created: number;
  updated: number;
}

export interface SalesContact {
  id: string;
  company_id: string;
  name: string;
  role: string;
  email: string;
  phone: string;
  is_decision_maker: boolean;
  source: string;
  created: number;
}

export interface SalesLead {
  id: string;
  company_id: string;
  prospect_id: string;
  stage: PipelineStage;
  source: string;
  dedupe_key: string;
  score: number;
  score_version: number;
  owner: string;
  experiment_id: string;
  lost_reason: string;
  next_action: string;
  next_action_due: string;
  created: number;
  updated: number;
  // joined (api/v1/sales/lead) — not always present
  company_name?: string;
  industry?: string;
}

export interface SalesEvidence {
  id: string;
  lead_id: string;
  claim_type: string;
  claim_text: string;
  source_ref: string;
  tier: ClaimTier;
  excerpt: string;
  run_id: string;
  observation_id: string;
  confidence: number;
  created: number;
}

export interface PainPoint {
  id: string;
  lead_id: string;
  text: string;
  category: string;
  severity: number;
  frequency: number;
  revenue_impact: number;
  automation_potential: number;
  implementation_difficulty: number;
  opportunity_score: number;
  tier: ClaimTier;
  evidence_ids: string[];
  created: number;
}

export interface Qualification {
  id: string;
  lead_id: string;
  version: number;
  icp_fit: number;
  pain_signal: number;
  urgency: number;
  economic_potential: number;
  accessibility: number;
  confidence: number;
  score: number;
  tier: ClaimTier;
  signals: Record<string, unknown>;
  evidence_ids: string[];
  reasoning: string;
  model: string;
  model_version: string;
  run_id: string;
  created: number;
}

export interface OutreachDraft {
  id: string;
  lead_id: string;
  channel: string;
  subject: string;
  body: string;
  contact_id: string;
  state: OutreachState;
  sequence_step: string;
  variant: string;
  experiment_id: string;
  evidence_ids: string[];
  approved_by: string;
  approved_at: number;
  sent_at: number;
  receipt: string;
  run_id: string;
  created: number;
}

export interface ICP {
  id: string;
  name: string;
  industry: string;
  min_team_size: number;
  geography: string;
  rank: number;
  rank_score: number;
  offer: string;
  offer_price: number;
  source_doc: string;
  active: boolean;
  created: number;
}

export interface StageTransition {
  id: string;
  lead_id: string;
  from_stage: string;
  to_stage: string;
  reason: string;
  run_id: string;
  worker: string;
  created: number;
}

export interface LeadDetail extends SalesLead {
  evidence: SalesEvidence[];
  qualifications: Qualification[];
  pain_points: PainPoint[];
  drafts: OutreachDraft[];
  stage_history: StageTransition[];
  company?: SalesCompany;
  contacts?: SalesContact[];
}

export interface SalesMetrics {
  date: string;
  vs_target: Record<string, { actual: number; target: number; met: boolean }>;
  failed_sales_day: boolean | null;
  [k: string]: unknown;
}

// ---------------------------------------------------------------------------
// Audit / security (sworker/security_events.py)
// ---------------------------------------------------------------------------

export interface SecurityEvent {
  kind: string;
  label: string;
  summary: string;
  severity: string;
  ts: number;
  actor: string;
}

export interface AuditEntry {
  ts: number;
  event: string;
  table: string;
  id: string;
}

export interface AuditChainStatus {
  ok: boolean;
  checked: number;
  lines: number;
}

// ---------------------------------------------------------------------------
// Top-level API contract mirror (/api/v1/*)
// ---------------------------------------------------------------------------

export interface DashboardPayload {
  workspace: string;
  health: { ok: boolean; checks: HealthCheck[] };
  workers: string[];
  runs_total: number;
  runs_by_status: Record<string, number>;
  pending_approvals: number;
  metrics: { runs_total: number; evidence: number; artifacts: number; tool_failures: number };
}

export interface HealthCheck {
  name: string;
  severity: string;
  status: string;
  source: string;
}

export interface SystemStatusPayload {
  verdict: string;
  controls: Array<{
    severity: string;
    name: string;
    status: string;
    source: string;
  }>;
}

export interface InspectorPayload {
  id: string;
  seq: number;
  worker: string;
  status: RunStatus;
  intent: string;
  summary: string;
  timeline: Array<{ kind: TimelineKind; text: string }>;
}

export interface Workspace {
  root: string;
}

/** A single run fully assembled for the Run Detail screen. */
export interface RunBundle {
  run: RunRecord;
  task: TaskRecord;
  plan: PlanRecord | null;
  steps: StepRecord[];
  actions: ActionRecord[];
  observations: ObservationRecord[];
  evidence: EvidenceRecord[];
  claims: ClaimRecord[];
  verifications: VerificationRecord[];
  approvals: ApprovalRecord[];
  artifacts: ArtifactRecord[];
  timeline: TimelineEvent[];
  audit: AuditEntry[];
}

export const DEMO_BANNER = "DEMO DATASET — mirrors the live /api/v1 contract. Not a live workspace.";

/** Flattened evidence for the Evidence Explorer list (run + provenance context). */
export interface EvidenceListEntry {
  id: string;
  run_id: string;
  provenance: Provenance;
  summary: string;
  source_ref: string;
  excerpt: string;
  observation_id: string;
  created: number;
  claim_ids?: string[];
}

export interface ApprovalListEntry {
  id: string;
  run_id: string;
  worker: string;
  action_id: string;
  risk: RiskLevel;
  summary: string;
  state: ApprovalState;
  reason: string;
  evidence_ids: string[];
  created: number;
  decided_by: string;
}

export interface AuditChainStatus {
  ok: boolean;
  checked: number;
  lines: number;
}

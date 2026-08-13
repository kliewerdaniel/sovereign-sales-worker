import type {
  ApprovalListEntry,
  ArtifactRecord,
  AuditChainStatus,
  AuditEntry,
  DashboardPayload,
  EvidenceListEntry,
  InspectorPayload,
  LeadDetail,
  RunBundle,
  RunRecord,
  SecurityEvent,
  SystemStatusPayload,
  ToolSpec,
  WorkerConfig,
} from "./types";
import {
  DEMO_AUDIT_CHAIN,
  DEMO_DAILY_METRICS,
  DEMO_LEADS,
  DEMO_RUN_BUNDLES,
  DEMO_SECURITY_EVENTS,
  DEMO_TOOLS,
  DEMO_WORKERS,
  demoLeadDetail,
  demoRunBundle,
  demoRunList,
} from "./data/demo";

/**
 * Backend adapter. The UI depends ONLY on this interface — never on a specific
 * data source. The default implementation is a deterministic demo dataset that
 * conforms to the runtime's real /api/v1 JSON contract. To point at a live
 * workspace, implement `Backend` against the stdlib HTTP server (see
 * sworker/web.py /api/v1) and pass it through <BackendProvider>.
 */

export interface Backend {
  readonly source: "demo" | "live";
  /** Banner shown in the UI when data is not a live workspace. */
  readonly notice?: string;
  getDashboard(): Promise<DashboardPayload>;
  listRuns(): Promise<RunRecord[]>;
  getRun(runId: string): Promise<RunBundle | null>;
  getInspector(runId: string): Promise<InspectorPayload | null>;
  listWorkers(): Promise<WorkerConfig[]>;
  getWorker(name: string): Promise<WorkerConfig | null>;
  listTools(): Promise<ToolSpec[]>;
  getTool(name: string): Promise<ToolSpec | null>;
  getSystemStatus(): Promise<SystemStatusPayload>;
  getSecurityEvents(): Promise<{ events: SecurityEvent[]; chain: AuditChainStatus }>;
  getAudit(runId: string): Promise<AuditEntry[]>;
  listLeads(): Promise<LeadDetail[]>;
  getLead(leadId: string): Promise<LeadDetail | null>;
  getDailyMetrics(): Promise<typeof DEMO_DAILY_METRICS>;
  listEvidence(): Promise<EvidenceListEntry[]>;
  listArtifacts(): Promise<ArtifactRecord[]>;
  listApprovals(): Promise<ApprovalListEntry[]>;
  auditChain(): Promise<AuditChainStatus>;
}

function outEvidenceCount(): number {
  let n = 0;
  for (const b of Object.values(DEMO_RUN_BUNDLES)) n += b.evidence.length;
  return n;
}

function outArtifactCount(): number {
  let n = 0;
  for (const b of Object.values(DEMO_RUN_BUNDLES)) n += b.artifacts.length;
  return n;
}

function dashboard(): DashboardPayload {
  const runs = demoRunList();
  const by: Record<string, number> = {};
  for (const r of runs) by[r.status] = (by[r.status] ?? 0) + 1;
  return {
    workspace: "/demo/sovereign-sales-worker",
    health: { ok: true, checks: [{ name: "ledger", severity: "ok", status: "writable", source: "store" }] },
    workers: DEMO_WORKERS.map((w) => w.name),
    runs_total: runs.length,
    runs_by_status: by,
    pending_approvals: runs.reduce(
      (n, r) => n + (r.status === "AWAITING_APPROVAL" ? 1 : 0),
      0,
    ),
    metrics: {
      runs_total: runs.length,
      evidence: outEvidenceCount(),
      artifacts: outArtifactCount(),
      tool_failures: 0,
    },
  };
}

function inspector(runId: string): InspectorPayload | null {
  const b = DEMO_RUN_BUNDLES[runId] ?? (runId === demoRunBundle().run.id ? demoRunBundle() : null);
  if (!b) return null;
  return {
    id: b.run.id,
    seq: b.run.seq,
    worker: b.run.worker,
    status: b.run.status,
    intent: b.run.intent,
    summary: b.run.summary,
    timeline: b.timeline.map((e) => ({ kind: e.kind, text: e.title })),
  };
}

export const demoBackend: Backend = {
  source: "demo",
  notice:
    "DEMO DATASET — mirrors the live /api/v1 contract. Not connected to a live workspace. Set SOVEREIGN_API_BASE to attach a real worker.",
  getDashboard: async () => dashboard(),
  listRuns: async () => demoRunList(),
  getRun: async (id) => DEMO_RUN_BUNDLES[id] ?? null,
  getInspector: async (id) => inspector(id),
  listWorkers: async () => DEMO_WORKERS,
  getWorker: async (name) => DEMO_WORKERS.find((w) => w.name === name) ?? null,
  listTools: async () => DEMO_TOOLS,
  getTool: async (name) => DEMO_TOOLS.find((t) => t.name === name) ?? null,
  getSystemStatus: async () => ({
    verdict: "ok",
    controls: [
      { severity: "ok", name: "auth", status: "local accounts + RBAC", source: "auth.py" },
      { severity: "ok", name: "policy", status: "default-deny egress", source: "config.py" },
      { severity: "ok", name: "ledger", status: "hash-chained, append-only", source: "store.py" },
      { severity: "warning", name: "sandbox", status: "host (shallow) — docker opt-in", source: "config.py" },
      { severity: "ok", name: "decomposition", status: "guard active", source: "engine.py" },
    ],
  }),
  getSecurityEvents: async () => ({
    events: DEMO_SECURITY_EVENTS as SecurityEvent[],
    chain: DEMO_AUDIT_CHAIN,
  }),
  getAudit: async (id) => DEMO_RUN_BUNDLES[id]?.audit ?? [],
  listLeads: async () =>
    DEMO_LEADS.map((l) => ({ ...l, evidence: [], qualifications: [], pain_points: [], drafts: [], stage_history: [] })),
  getLead: async (id) => demoLeadDetail(id),
  getDailyMetrics: async () => DEMO_DAILY_METRICS,
  listEvidence: async () => {
    const out: EvidenceListEntry[] = [];
    for (const b of Object.values(DEMO_RUN_BUNDLES)) {
      for (const e of b.evidence) {
        out.push({
          id: e.id,
          run_id: e.run_id,
          provenance: e.provenance,
          summary: e.summary,
          source_ref: e.source_ref,
          excerpt: e.excerpt,
          observation_id: e.observation_id,
          created: e.created,
          claim_ids: b.claims.filter((c) => c.evidence_ids.includes(e.id)).map((c) => c.id),
        });
      }
    }
    return out;
  },
  listArtifacts: async () => {
    const out: ArtifactRecord[] = [];
    for (const b of Object.values(DEMO_RUN_BUNDLES)) out.push(...b.artifacts);
    return out;
  },
  listApprovals: async () => {
    const out: ApprovalListEntry[] = [];
    for (const b of Object.values(DEMO_RUN_BUNDLES)) {
      for (const a of b.approvals) {
        out.push({
          id: a.id,
          run_id: b.run.id,
          worker: b.run.worker,
          action_id: a.action_id,
          risk: a.risk,
          summary: a.summary,
          state: a.state,
          reason: a.reason,
          evidence_ids: a.evidence_ids,
          created: a.created,
          decided_by: a.decided_by,
        });
      }
    }
    return out;
  },
  auditChain: async () => DEMO_AUDIT_CHAIN,
};

/**
 * Live backend (stub). Implemented against sworker/web.py /api/v1. Wired via
 * rewrites (next.config.ts, SOVEREIGN_API_BASE). Throwing here is intentional —
 * the app falls back to demo unless a real backend is provided.
 */
export function createLiveBackend(baseUrl: string): Backend {
  const get = async (path: string) => {
    const res = await fetch(`${baseUrl.replace(/\/$/, "")}${path}`, { cache: "no-store" });
    if (!res.ok) throw new Error(`${path} → ${res.status}`);
    return res.json();
  };
  return {
    source: "live",
    getDashboard: () => get("/dashboard"),
    listRuns: () => get("/runs"),
    getRun: async (id) => get(`/runs/${id}`),
    getInspector: async (id) => get(`/inspect/${id}`),
    listWorkers: () => get("/workers"),
    getWorker: async () => null,
    listTools: async () => [],
    getTool: async () => null,
    getSystemStatus: () => get("/status"),
    getSecurityEvents: () => get("/security"),
    getAudit: async (id) => get(`/runs/${id}`).then((r) => r.audit ?? []),
    listLeads: () => get("/sales/pipeline"),
    getLead: async (id) => get(`/sales/lead/${id}`),
    getDailyMetrics: async () => get("/sales/metrics"),
    listEvidence: async () => get("/evidence"),
    listArtifacts: async () => get("/artifacts"),
    listApprovals: async () => get("/approvals"),
    auditChain: async () => get("/security").then((r) => r.chain ?? { ok: false, checked: 0, lines: 0 }),
  };
}

export function resolveBackend(): Backend {
  const base = process.env.NEXT_PUBLIC_SOVEREIGN_API_BASE;
  if (base) {
    try {
      return createLiveBackend(base);
    } catch {
      return demoBackend;
    }
  }
  return demoBackend;
}

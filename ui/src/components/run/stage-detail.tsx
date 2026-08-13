"use client";

import { cn } from "@/lib/cn";
import type { RunBundle } from "@/lib/types";
import type { GraphSelection } from "@/components/run/execution-graph";
import type { StageNode } from "@/lib/run-graph";
import {
  ActionStatusBadge,
  ApprovalBadge,
  Badge,
  Hash,
  ProvenanceBadge,
  RefId,
  RiskBadge,
  VerifyBadge,
} from "@/components/ui/primitives";

/** Resolves a selected lifecycle stage to its concrete run records and renders
 *  them — this is where a reviewer sees *why* a decision was made and what
 *  evidence supports it. */
export function StageDetail({
  selection,
  bundle,
  onFocusKey,
}: {
  nodes: StageNode[];
  selection: GraphSelection;
  bundle: RunBundle;
  onFocusKey?: (k: string) => void;
}) {
  const { key, refs } = selection;
  const b = bundle;

  return (
    <div className="surface p-4">
      {key === "REQUEST" || key === "INTENT" ? (
        <KeyValue label={key} value={key === "REQUEST" ? b.task.request : b.task.intent} id={b.task.id} />
      ) : null}

      {key === "PLAN" ? <PlanView bundle={b} /> : null}

      {key === "ACTION" || key === "TOOL" ? (
        <ActionList ids={refs} bundle={b} onFocus={(k) => onFocusKey?.(k)} />
      ) : null}

      {key === "OBSERVATION" ? <ObservationList ids={refs} bundle={b} /> : null}

      {key === "EVIDENCE" ? <EvidenceList ids={refs} bundle={b} onFocusClaim={() => onFocusKey?.("CLAIM")} /> : null}

      {key === "CLAIM" ? <ClaimList bundle={b} /> : null}

      {key === "VERIFY" ? <VerifyList bundle={b} /> : null}

      {key === "ARTIFACT" ? <ArtifactList ids={refs} bundle={b} /> : null}

      {key === "APPROVAL" ? <ApprovalList bundle={b} /> : null}

      {key === "FINAL" ? <FinalView bundle={b} /> : null}

      {key === "AUDIT" ? <AuditView bundle={b} /> : null}

      {key === "BLOCK" ? <BlockView bundle={b} /> : null}
    </div>
  );
}

function KeyValue({ label, value, id }: { label: string; value: string; id: string }) {
  return (
    <div>
      <div className="mb-1.5 flex items-center gap-2">
        <span className="text-xs font-semibold text-ink-1">{label}</span>
        <RefId value={id} />
      </div>
      <p className="text-sm leading-relaxed text-ink-2">{value}</p>
    </div>
  );
}

function PlanView({ bundle }: { bundle: RunBundle }) {
  const p = bundle.plan;
  if (!p) return <p className="text-sm text-ink-3">No plan recorded.</p>;
  return (
    <div>
      <div className="mb-2 flex items-center gap-2">
        <span className="text-xs font-semibold text-ink-1">Procedure-grounded plan</span>
        <RefId value={p.id} />
        <Badge tone="neutral">{p.source}</Badge>
      </div>
      <p className="mb-3 text-sm leading-relaxed text-ink-2">{p.rationale}</p>
      <ol className="space-y-1.5">
        {bundle.steps.map((s, i) => (
          <li key={s.id} className="flex items-start gap-2.5 rounded-md border border-hairline-soft bg-surface-2/50 px-3 py-2">
            <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-surface-4 text-[11px] text-ink-2">
              {i + 1}
            </span>
            <div className="min-w-0">
              <div className="text-sm text-ink-1">{s.description}</div>
              <div className="mt-0.5 flex items-center gap-2 text-xs text-ink-3">
                <span className="mono">{s.tool}</span>
                <RefId value={s.id} />
              </div>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

function ActionList({
  ids,
  bundle,
  onFocus,
}: {
  ids: string[];
  bundle: RunBundle;
  onFocus: (k: string) => void;
}) {
  const actions = bundle.actions.filter((a) => ids.includes(a.id));
  return (
    <div className="space-y-2">
      {actions.map((a) => (
        <div key={a.id} className="rounded-md border border-hairline-soft bg-surface-2/50 px-3 py-2.5">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="mono text-sm text-ink-0">{a.tool}</span>
              <ActionStatusBadge status={a.status} />
              <RiskBadge risk={a.risk} />
            </div>
            <RefId value={a.id} />
          </div>
          <p className="mt-1.5 text-sm text-ink-2">{a.summary}</p>
          {a.reason ? (
            <p className={cn("mt-1.5 rounded border px-2 py-1.5 text-xs", a.status === "DENIED" || a.status === "REJECTED" ? "border-block/30 bg-block/10 text-block" : "border-hairline-soft bg-surface-3/40 text-ink-3")}>
              {a.reason}
            </p>
          ) : null}
          {a.approval_id ? (
            <button onClick={() => onFocus("APPROVAL")} className="mt-1.5 text-xs text-accent hover:underline">
              linked approval · {a.approval_id}
            </button>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function ObservationList({ ids, bundle }: { ids: string[]; bundle: RunBundle }) {
  const obs = bundle.observations.filter((o) => ids.includes(o.id));
  if (!obs.length) return <p className="text-sm text-ink-3">No observations for this stage.</p>;
  return (
    <div className="space-y-2">
      {obs.map((o) => (
        <div key={o.id} className="rounded-md border border-hairline-soft bg-surface-2/50 px-3 py-2.5">
          <div className="flex items-center justify-between">
            <span className={cn("text-xs font-medium", o.ok ? "text-ok" : "text-bad")}>
              {o.ok ? "OBSERVED · OK" : "OBSERVED · FAIL"}
            </span>
            <RefId value={o.id} />
          </div>
          <p className="mono mt-1.5 whitespace-pre-wrap text-xs leading-relaxed text-ink-2">{o.output}</p>
          {o.injection ? (
            <p className="mt-1.5 rounded border border-warn/30 bg-warn/10 px-2 py-1 text-xs text-warn">
              INJECTION FLAG: {o.injection}
            </p>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function EvidenceList({
  ids,
  bundle,
  onFocusClaim,
}: {
  ids: string[];
  bundle: RunBundle;
  onFocusClaim: () => void;
}) {
  const ev = bundle.evidence.filter((e) => ids.includes(e.id));
  return (
    <div className="space-y-2">
      {ev.map((e) => (
        <div key={e.id} className="rounded-md border border-hairline-soft bg-surface-2/50 px-3 py-2.5">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <ProvenanceBadge p={e.provenance} />
              <RefId value={e.id} />
            </div>
            <button onClick={onFocusClaim} className="text-xs text-accent hover:underline">
              {e.observation_id}
            </button>
          </div>
          <p className="mt-1.5 text-sm text-ink-1">{e.summary}</p>
          {e.excerpt ? (
            <blockquote className="mt-1.5 border-l-2 border-accent/40 pl-2.5 text-xs italic text-ink-3">
              “{e.excerpt}”
            </blockquote>
          ) : null}
          <div className="mt-1.5 flex items-center gap-2 text-xs text-ink-3">
            <span>source</span>
            <span className="mono truncate text-ink-2">{e.source_ref}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function ClaimList({ bundle }: { bundle: RunBundle }) {
  if (!bundle.claims.length) return <p className="text-sm text-ink-3">No claims asserted in this run.</p>;
  return (
    <div className="space-y-2.5">
      {bundle.claims.map((c) => (
        <div key={c.id} className="rounded-md border border-hairline-soft bg-surface-2/50 px-3 py-2.5">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Badge tone={c.refuted ? "bad" : c.provenance === "OBSERVED" || c.provenance === "VERIFIED" || c.provenance === "CLIENT_VERIFIED" || c.provenance === "CASE_STUDY" ? "ok" : c.provenance === "HYPOTHESIS" ? "warn" : "neutral"}>
                {c.provenance}
              </Badge>
              <RefId value={c.id} />
            </div>
            <Badge tone="neutral">{c.confidence}</Badge>
          </div>
          <p className="mt-1.5 text-sm text-ink-1">{c.text}</p>
          {c.evidence_ids.length ? (
            <div className="mt-1.5 flex flex-wrap items-center gap-1 text-xs text-ink-3">
              <span>evidence</span>
              {c.evidence_ids.map((e) => (
                <span key={e} className="mono rounded border border-hairline-soft bg-surface-3/50 px-1.5 py-0.5 text-[10px] text-accent/80">
                  {e}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function VerifyList({ bundle }: { bundle: RunBundle }) {
  if (!bundle.verifications.length) return <p className="text-sm text-ink-3">No verification checks.</p>;
  return (
    <div className="space-y-2">
      {bundle.verifications.map((v) => (
        <div key={v.id} className="rounded-md border border-hairline-soft bg-surface-2/50 px-3 py-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <VerifyBadge outcome={v.outcome} />
              <span className="mono text-xs text-ink-2">{v.check}</span>
            </div>
            <RefId value={v.id} />
          </div>
          <p className="mt-1.5 text-sm text-ink-2">{v.detail}</p>
          <div className="mt-1.5 grid grid-cols-2 gap-2 text-xs">
            <div className="rounded border border-hairline-soft bg-surface-3/30 px-2 py-1">
              <div className="text-ink-4">expected</div>
              <div className="mono text-ink-2">{v.expected}</div>
            </div>
            <div className="rounded border border-hairline-soft bg-surface-3/30 px-2 py-1">
              <div className="text-ink-4">actual</div>
              <div className="mono text-ink-2">{v.actual}</div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function ArtifactList({ ids, bundle }: { ids: string[]; bundle: RunBundle }) {
  const arts = bundle.artifacts.filter((a) => ids.includes(a.id));
  return (
    <div className="space-y-2">
      {arts.map((a) => (
        <div key={a.id} className="rounded-md border border-hairline-soft bg-surface-2/50 px-3 py-2.5">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Badge tone="accent">{a.kind}</Badge>
              <span className="text-sm text-ink-0">{a.title}</span>
            </div>
            <RefId value={a.id} />
          </div>
          <p className="mt-1.5 text-xs text-ink-3">{a.path}</p>
          <Hash value={a.sha256} />
        </div>
      ))}
    </div>
  );
}

function ApprovalList({ bundle }: { bundle: RunBundle }) {
  if (!bundle.approvals.length) return <p className="text-sm text-ink-3">No approval requests in this run.</p>;
  return (
    <div className="space-y-2.5">
      {bundle.approvals.map((a) => (
        <div key={a.id} className="rounded-md border border-hairline-soft bg-surface-2/50 px-3 py-2.5">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <ApprovalBadge state={a.state} />
              <RiskBadge risk={a.risk} />
              <RefId value={a.id} />
            </div>
            <span className="text-xs text-ink-3">quorum {a.quorum}</span>
          </div>
          <p className="mt-1.5 text-sm text-ink-1">{a.summary}</p>
          {a.reason ? <p className="mt-1.5 text-xs text-ink-3">{a.reason}</p> : null}
          {a.evidence_ids.length ? (
            <div className="mt-1.5 flex flex-wrap items-center gap-1 text-xs">
              <span className="text-ink-4">supporting</span>
              {a.evidence_ids.map((e) => (
                <span key={e} className="mono rounded border border-hairline-soft bg-surface-3/50 px-1.5 py-0.5 text-[10px] text-accent/80">
                  {e}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function FinalView({ bundle }: { bundle: RunBundle }) {
  return (
    <div>
      <div className="mb-2 flex items-center gap-2">
        <Badge tone={bundle.run.status === "SUCCESS" ? "ok" : bundle.run.status === "FAILED" ? "bad" : "warn"}>
          {bundle.run.status}
        </Badge>
        <RefId value={bundle.run.id} />
      </div>
      <p className="text-sm leading-relaxed text-ink-2">{bundle.run.summary}</p>
      {bundle.run.error ? (
        <p className="mt-2 rounded border border-bad/30 bg-bad/10 px-2 py-1.5 text-xs text-bad">{bundle.run.error}</p>
      ) : null}
    </div>
  );
}

function AuditView({ bundle }: { bundle: RunBundle }) {
  return (
    <div>
      <p className="mb-2 text-xs text-ink-3">
        Every mutation is hash-chained and append-only. This run contributed {bundle.audit.length} entries.
      </p>
      <ul className="space-y-1">
        {bundle.audit.map((a, i) => (
          <li key={i} className="flex items-center justify-between rounded border border-hairline-soft bg-surface-2/40 px-2.5 py-1.5 text-xs">
            <span className="mono text-ink-1">{a.event}</span>
            <span className="mono text-ink-4">{a.id}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function BlockView({ bundle }: { bundle: RunBundle }) {
  const blocked = bundle.actions.filter((a) => a.status === "DENIED" || a.status === "REJECTED");
  if (!blocked.length) return <p className="text-sm text-ink-3">No blocked actions.</p>;
  return (
    <div className="space-y-2">
      {blocked.map((a) => (
        <div key={a.id} className="rounded-md border border-block/30 bg-block/10 px-3 py-2.5">
          <div className="flex items-center gap-2">
            <Badge tone="block">{a.risk} · blocked</Badge>
            <RefId value={a.id} />
          </div>
          <p className="mt-1.5 text-sm text-ink-1">{a.summary}</p>
          <p className="mt-1.5 text-xs text-block">{a.reason}</p>
        </div>
      ))}
    </div>
  );
}

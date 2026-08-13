"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useBackend } from "@/components/providers/backend-provider";
import { useAsync } from "@/lib/use-async";
import { Badge, EmptyState, RiskBadge, ApprovalBadge, Hash, RefId } from "@/components/ui/primitives";
import { fmtTime } from "@/lib/domain";
import { cn } from "@/lib/cn";
import { ListChecks, Inbox, Clock } from "lucide-react";
import type { ApprovalListEntry, ApprovalState } from "@/lib/types";

const FILTERS: Array<{ key: ApprovalState | "ALL"; label: string }> = [
  { key: "ALL", label: "All" },
  { key: "PENDING", label: "Pending" },
  { key: "APPROVED", label: "Approved" },
  { key: "REJECTED", label: "Rejected" },
  { key: "EXPIRED", label: "Expired" },
];

export default function ApprovalsPage() {
  const backend = useBackend();
  const { data, loading } = useAsync(() => backend.listApprovals(), []);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<ApprovalState | "ALL">("ALL");

  const items = data ?? [];
  const filtered = useMemo(() => {
    let out = items;
    if (filter !== "ALL") out = out.filter((a) => a.state === filter);
    if (q.trim()) {
      const l = q.toLowerCase();
      out = out.filter((a) => `${a.id} ${a.summary} ${a.worker} ${a.risk}`.toLowerCase().includes(l));
    }
    return [...out].sort((a, b) => b.created - a.created);
  }, [items, filter, q]);

  const pending = items.filter((a) => a.state === "PENDING").length;

  return (
    <div className="mx-auto max-w-7xl px-5 py-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-ink-0">Approvals</h1>
          <p className="mt-1 text-sm text-ink-3">
            The human-in-the-loop gate. Nothing with egress or financial risk proceeds without one of these.
          </p>
        </div>
        <div className="relative w-full max-w-xs">
          <ListChecks className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search approvals…"
            className="w-full rounded-md border border-hairline-soft bg-surface-1 py-2 pl-9 pr-3 text-sm text-ink-0 outline-none placeholder:text-ink-3 focus:border-hairline"
            aria-label="Search approvals"
          />
        </div>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        <div className="surface px-3.5 py-3">
          <div className="text-[11px] uppercase tracking-wider text-ink-3">Total requests</div>
          <div className="mt-1 text-2xl font-semibold tabular-nums text-ink-0">{items.length}</div>
        </div>
        <div className="surface px-3.5 py-3">
          <div className="text-[11px] uppercase tracking-wider text-ink-3">Awaiting decision</div>
          <div className="mt-1 flex items-center gap-2 text-2xl font-semibold tabular-nums text-warn">
            <Clock className="h-5 w-5" /> {pending}
          </div>
        </div>
        <div className="surface px-3.5 py-3">
          <div className="text-[11px] uppercase tracking-wider text-ink-3">Decided</div>
          <div className="mt-1 text-2xl font-semibold tabular-nums text-ok">
            {items.filter((a) => a.state !== "PENDING").length}
          </div>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-1.5 border-b border-hairline-soft pb-3">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={cn(
              "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
              filter === f.key ? "bg-surface-3 text-ink-0" : "text-ink-3 hover:text-ink-1",
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="mt-4 space-y-2.5">
        {!loading && filtered.length === 0 ? (
          <EmptyState icon={<Inbox className="h-8 w-8" />} title="No approvals" body="No human-gate requests for this filter." />
        ) : loading ? (
          [0, 1, 2].map((i) => <div key={i} className="surface h-[110px] animate-pulse" />)
        ) : (
          filtered.map((a) => <ApprovalRow key={a.id} a={a} />)
        )}
      </div>
    </div>
  );
}

function ApprovalRow({ a }: { a: ApprovalListEntry }) {
  return (
    <div className="surface px-4 py-3.5">
      <div className="flex flex-wrap items-center gap-2.5">
        <ApprovalBadge state={a.state} />
        <RiskBadge risk={a.risk} />
        <span className="mono text-[11px] text-ink-3">{a.id}</span>
        <Link href={`/runs/${a.run_id}`} className="mono text-[11px] text-ink-3 hover:text-accent">
          {a.run_id}
        </Link>
        <span className="ml-auto text-[11px] text-ink-3">{fmtTime(a.created)}</span>
      </div>
      <p className="mt-2 text-sm text-ink-1">{a.summary}</p>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px] text-ink-3">
        <span>
          worker <Badge tone="neutral">{a.worker}</Badge>
        </span>
        <span className="flex items-center gap-1.5">
          action <RefId value={a.action_id} />
        </span>
        {a.evidence_ids.length > 0 ? (
          <span className="flex items-center gap-1.5">
            evidence
            {a.evidence_ids.map((e) => (
              <RefId key={e} value={e} />
            ))}
          </span>
        ) : null}
        {a.decided_by ? (
          <span className="ml-auto text-ink-4">decided by {a.decided_by}</span>
        ) : null}
      </div>
      {a.reason ? (
        <p className="mt-2 border-l-2 border-hairline-soft pl-3 text-[13px] leading-relaxed text-ink-3">{a.reason}</p>
      ) : null}
    </div>
  );
}

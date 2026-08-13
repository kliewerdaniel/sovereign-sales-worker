"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useBackend } from "@/components/providers/backend-provider";
import { useAsync } from "@/lib/use-async";
import { RunStatusBadge, EmptyState, Badge } from "@/components/ui/primitives";
import { fmtDuration, fmtTime } from "@/lib/domain";
import { cn } from "@/lib/cn";
import { Search, Inbox } from "lucide-react";
import type { RunRecord, RunStatus } from "@/lib/types";

const STATUS_FILTERS: Array<{ key: RunStatus | "ALL"; label: string }> = [
  { key: "ALL", label: "All" },
  { key: "SUCCESS", label: "Success" },
  { key: "PARTIAL_SUCCESS", label: "Partial" },
  { key: "AWAITING_APPROVAL", label: "Awaiting" },
  { key: "FAILED", label: "Failed" },
  { key: "BLOCKED", label: "Blocked" },
];

const SORTS = [
  { key: "started", label: "Newest" },
  { key: "evidence", label: "Evidence" },
  { key: "actions", label: "Actions" },
] as const;

export default function RunsPage() {
  const backend = useBackend();
  const { data, loading } = useAsync(() => backend.listRuns(), []);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<RunStatus | "ALL">("ALL");
  const [sort, setSort] = useState<(typeof SORTS)[number]["key"]>("started");

  const runs = data ?? [];
  const filtered = useMemo(() => {
    let out = runs;
    if (status !== "ALL") out = out.filter((r) => r.status === status);
    if (q.trim()) {
      const l = q.toLowerCase();
      out = out.filter((r) => `${r.id} ${r.intent} ${r.worker} ${r.procedure}`.toLowerCase().includes(l));
    }
    out = [...out].sort((a, b) =>
      sort === "started" ? b.started - a.started : sort === "evidence" ? b.evidence_count - a.evidence_count : b.approval_count - a.approval_count,
    );
    return out;
  }, [runs, status, q, sort]);

  const counts = useMemo(() => {
    const c: Record<string, number> = { ALL: runs.length };
    for (const r of runs) c[r.status] = (c[r.status] ?? 0) + 1;
    return c;
  }, [runs]);

  return (
    <div className="mx-auto max-w-7xl px-5 py-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-ink-0">Run Explorer</h1>
          <p className="mt-1 text-sm text-ink-3">
            Every execution the worker has performed — inspectable end to end.
          </p>
        </div>
        <div className="relative w-full max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search runs…"
            className="w-full rounded-md border border-hairline-soft bg-surface-1 py-2 pl-9 pr-3 text-sm text-ink-0 outline-none placeholder:text-ink-3 focus:border-hairline"
            aria-label="Search runs"
          />
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3 border-b border-hairline-soft pb-3">
        <div className="flex flex-wrap gap-1.5">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => setStatus(f.key)}
              className={cn(
                "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                status === f.key ? "bg-surface-3 text-ink-0" : "text-ink-3 hover:text-ink-1",
              )}
            >
              {f.label}
              <span className="ml-1.5 text-ink-4">{counts[f.key] ?? 0}</span>
            </button>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-2 text-xs text-ink-3">
          <span>Sort</span>
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as (typeof SORTS)[number]["key"])}
            className="rounded-md border border-hairline-soft bg-surface-1 px-2 py-1 text-ink-1 outline-none"
          >
            {SORTS.map((s) => (
              <option key={s.key} value={s.key}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="mt-4 space-y-2.5">
        {!loading && filtered.length === 0 ? (
          <EmptyState
            icon={<Inbox className="h-8 w-8" />}
            title="No runs match this filter"
            body="Adjust the status filter or search query, or clear them to see every execution."
          />
        ) : loading ? (
          [0, 1, 2].map((i) => <div key={i} className="surface h-[96px] animate-pulse" />)
        ) : (
          filtered.map((r) => <RunRow key={r.id} run={r} />)
        )}
      </div>
    </div>
  );
}

function RunRow({ run }: { run: RunRecord }) {
  return (
    <Link href={`/runs/${run.id}`}>
      <div className="surface group flex items-center gap-4 px-4 py-3 transition-colors hover:border-hairline">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2.5">
            <RunStatusBadge status={run.status} />
            <span className="mono text-[11px] text-ink-3">{run.id}</span>
            <Badge tone="neutral">{run.worker}</Badge>
          </div>
          <p className="mt-1.5 truncate text-sm text-ink-1">{run.intent}</p>
        </div>
        <div className="hidden w-28 text-right text-xs text-ink-3 sm:block">{fmtTime(run.started)}</div>
        <div className="hidden w-24 text-right text-xs text-ink-3 md:block">
          {fmtDuration(run.started, run.finished)}        </div>
        <div className="hidden w-16 text-right text-xs text-ink-3 lg:block">
          <span className="text-accent">{run.evidence_count}</span> ev
        </div>
        <div className="hidden w-16 text-right text-xs text-ink-3 lg:block">
          <span className="text-block">{run.approval_count}</span> apr
        </div>
        <div className="w-10 text-right text-ink-3 transition-transform group-hover:translate-x-0.5">→</div>
      </div>
    </Link>
  );
}

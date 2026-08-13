"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useBackend } from "@/components/providers/backend-provider";
import { useAsync } from "@/lib/use-async";
import { EmptyState, ProvenanceBadge, Hash, RefId } from "@/components/ui/primitives";
import { fmtTime } from "@/lib/domain";
import { cn } from "@/lib/cn";
import { FileSearch, Inbox, ShieldAlert } from "lucide-react";
import type { EvidenceListEntry, Provenance } from "@/lib/types";

const FILTERS: Array<{ key: Provenance | "ALL"; label: string }> = [
  { key: "ALL", label: "All" },
  { key: "observed", label: "Observed" },
  { key: "inferred", label: "Inferred" },
  { key: "retrieved", label: "Retrieved" },
  { key: "verified", label: "Verified" },
  { key: "hypothesized", label: "Hypothesis" },
];

export default function EvidencePage() {
  const backend = useBackend();
  const { data, loading } = useAsync(() => backend.listEvidence(), []);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<Provenance | "ALL">("ALL");

  const items = data ?? [];
  const filtered = useMemo(() => {
    let out = items;
    if (filter !== "ALL") out = out.filter((e) => e.provenance === filter);
    if (q.trim()) {
      const l = q.toLowerCase();
      out = out.filter((e) =>
        `${e.id} ${e.summary} ${e.source_ref} ${e.excerpt}`.toLowerCase().includes(l),
      );
    }
    return [...out].sort((a, b) => b.created - a.created);
  }, [items, filter, q]);

  const counts = useMemo(() => {
    const c: Record<string, number> = { ALL: items.length };
    for (const e of items) c[e.provenance] = (c[e.provenance] ?? 0) + 1;
    return c;
  }, [items]);

  const observed = items.filter((e) => e.provenance === "observed" || e.provenance === "verified").length;

  return (
    <div className="mx-auto max-w-7xl px-5 py-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-ink-0">Evidence</h1>
          <p className="mt-1 text-sm text-ink-3">
            Every fact the worker asserted traces back to one of these records. No evidence, no claim.
          </p>
        </div>
        <div className="relative w-full max-w-xs">
          <FileSearch className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search evidence…"
            className="w-full rounded-md border border-hairline-soft bg-surface-1 py-2 pl-9 pr-3 text-sm text-ink-0 outline-none placeholder:text-ink-3 focus:border-hairline"
            aria-label="Search evidence"
          />
        </div>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        <div className="surface px-3.5 py-3">
          <div className="text-[11px] uppercase tracking-wider text-ink-3">Total evidence</div>
          <div className="mt-1 text-2xl font-semibold tabular-nums text-ink-0">{items.length}</div>
        </div>
        <div className="surface px-3.5 py-3">
          <div className="text-[11px] uppercase tracking-wider text-ink-3">Observed / verified</div>
          <div className="mt-1 text-2xl font-semibold tabular-nums text-ok">{observed}</div>
        </div>
        <div className="surface px-3.5 py-3">
          <div className="text-[11px] uppercase tracking-wider text-ink-3">Hypothesis only</div>
          <div className="mt-1 text-2xl font-semibold tabular-nums text-warn">
            {items.filter((e) => e.provenance === "hypothesized" || e.provenance === "inferred").length}
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
            <span className="ml-1.5 text-ink-4">{counts[f.key] ?? 0}</span>
          </button>
        ))}
      </div>

      <div className="mt-4 space-y-2.5">
        {!loading && filtered.length === 0 ? (
          <EmptyState
            icon={<Inbox className="h-8 w-8" />}
            title="No evidence matches"
            body="Adjust the provenance filter or search query."
          />
        ) : loading ? (
          [0, 1, 2].map((i) => <div key={i} className="surface h-[120px] animate-pulse" />)
        ) : (
          filtered.map((e) => <EvidenceRow key={e.id} e={e} />)
        )}
      </div>
    </div>
  );
}

function EvidenceRow({ e }: { e: EvidenceListEntry }) {
  return (
    <div className="surface px-4 py-3.5">
      <div className="flex flex-wrap items-center gap-2.5">
        <ProvenanceBadge p={e.provenance} />
        <Link href={`/runs/${e.run_id}`} className="mono text-[11px] text-ink-3 hover:text-accent">
          {e.run_id}
        </Link>
        {e.claim_ids && e.claim_ids.length > 0 ? (
          <span className="flex items-center gap-1 text-[11px] text-ink-3">
            supports
            {e.claim_ids.map((c) => (
              <RefId key={c} value={c} />
            ))}
          </span>
        ) : null}
        <span className="ml-auto text-[11px] text-ink-3">{fmtTime(e.created)}</span>
      </div>
      <p className="mt-2 text-sm text-ink-1">{e.summary}</p>
      <p className="mt-1.5 border-l-2 border-hairline-soft pl-3 text-[13px] italic leading-relaxed text-ink-3">
        “{e.excerpt}”
      </p>
      <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px] text-ink-3">
        <span className="flex items-center gap-1.5">
          <ShieldAlert className="h-3.5 w-3.5 text-ink-4" />
          source
          <code className="mono rounded bg-surface-3/60 px-1.5 py-0.5 text-ink-2">{e.source_ref}</code>
        </span>
        <Hash value={e.id} />
      </div>
    </div>
  );
}

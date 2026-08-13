"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useBackend } from "@/components/providers/backend-provider";
import { useAsync } from "@/lib/use-async";
import { Badge, EmptyState, Hash, Card } from "@/components/ui/primitives";
import { fmtTime, TONE_CLASS } from "@/lib/domain";
import type { Tone } from "@/lib/domain";
import { cn } from "@/lib/cn";
import { FileBox, Inbox, FileText } from "lucide-react";
import type { ArtifactRecord, ArtifactKind } from "@/lib/types";

const KIND_TONE: Record<ArtifactKind, Tone> = {
  markdown: "neutral",
  csv: "neutral",
  json: "neutral",
  png: "accent",
  code: "accent",
  message: "warn",
  report: "ok",
  list: "neutral",
  decision: "accent",
};

const FILTERS: Array<{ key: ArtifactKind | "ALL"; label: string }> = [
  { key: "ALL", label: "All" },
  { key: "report", label: "Reports" },
  { key: "markdown", label: "Docs" },
  { key: "message", label: "Drafts" },
  { key: "decision", label: "Decisions" },
];

export default function ArtifactsPage() {
  const backend = useBackend();
  const { data, loading } = useAsync(() => backend.listArtifacts(), []);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<ArtifactKind | "ALL">("ALL");

  const items = data ?? [];
  const filtered = useMemo(() => {
    let out = items;
    if (filter !== "ALL") out = out.filter((a) => a.kind === filter);
    if (q.trim()) {
      const l = q.toLowerCase();
      out = out.filter((a) => `${a.id} ${a.title} ${a.description} ${a.path}`.toLowerCase().includes(l));
    }
    return [...out].sort((a, b) => b.created - a.created);
  }, [items, filter, q]);

  return (
    <div className="mx-auto max-w-7xl px-5 py-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-ink-0">Artifacts</h1>
          <p className="mt-1 text-sm text-ink-3">
            Outputs the worker produced — reports, drafts, and decisions. Each has a sha256.
          </p>
        </div>
        <div className="relative w-full max-w-xs">
          <FileBox className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search artifacts…"
            className="w-full rounded-md border border-hairline-soft bg-surface-1 py-2 pl-9 pr-3 text-sm text-ink-0 outline-none placeholder:text-ink-3 focus:border-hairline"
            aria-label="Search artifacts"
          />
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

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {!loading && filtered.length === 0 ? (
          <div className="sm:col-span-2 lg:col-span-3">
            <EmptyState icon={<Inbox className="h-8 w-8" />} title="No artifacts" body="Nothing produced yet for this filter." />
          </div>
        ) : loading ? (
          [0, 1, 2, 3].map((i) => <div key={i} className="surface h-[180px] animate-pulse" />)
        ) : (
          filtered.map((a) => <ArtifactCard key={a.id} a={a} />)
        )}
      </div>
    </div>
  );
}

function ArtifactCard({ a }: { a: ArtifactRecord }) {
  return (
    <Card>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className={cn("rounded-md border p-1.5", TONE_CLASS[KIND_TONE[a.kind]].border, TONE_CLASS[KIND_TONE[a.kind]].bg)}>
            <FileText className={cn("h-4 w-4", TONE_CLASS[KIND_TONE[a.kind]].text)} />
          </span>
          <Badge tone={KIND_TONE[a.kind]}>{a.kind}</Badge>
        </div>
        <span className="text-[11px] text-ink-3">{fmtTime(a.created)}</span>
      </div>
      <h3 className="mt-3 text-sm font-medium text-ink-0">{a.title}</h3>
      <p className="mt-1 line-clamp-2 text-[13px] leading-relaxed text-ink-3">{a.description}</p>
      <div className="mt-3 space-y-1.5 font-mono text-[11px] text-ink-3">
        <div className="truncate">path: {a.path}</div>
        <div className="flex items-center justify-between">
          <span>{(a.bytes / 1024).toFixed(1)} KB</span>
          <span className="flex items-center gap-1.5">
            sha256 <Hash value={a.sha256} />
          </span>
        </div>
        <Link href={`/runs/${a.run_id}`} className="block text-accent hover:underline">
          {a.run_id}
        </Link>
      </div>
    </Card>
  );
}

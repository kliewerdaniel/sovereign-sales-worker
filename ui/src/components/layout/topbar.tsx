"use client";

import { useRouter } from "next/navigation";
import { useTheme } from "@/components/providers/theme-provider";
import { useCommandPalette } from "@/components/providers/command-palette-provider";
import { Badge } from "@/components/ui/primitives";
import { WorkerMark } from "@/components/ui/worker-mark";
import { Search, Command, Sun, Moon, Bell } from "lucide-react";
import { useBackend } from "@/components/providers/backend-provider";
import { useEffect, useRef, useState } from "react";
import type { RunRecord, SalesLead, ToolSpec, ArtifactRecord, EvidenceRecord } from "@/lib/types";

interface SearchHit {
  kind: "run" | "lead" | "tool" | "evidence" | "artifact";
  id: string;
  title: string;
  sub: string;
  href: string;
}

export function Topbar({ title }: { title: string }) {
  const { theme, toggle } = useTheme();
  const { toggle: togglePalette, setOpen } = useCommandPalette();
  const router = useRouter();
  const backend = useBackend();

  const [q, setQ] = useState("");
  const [open, setLocalOpen] = useState(false);
  const [hits, setHits] = useState<SearchHit[]>([]);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setLocalOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  useEffect(() => {
    if (!q.trim()) {
    // eslint-disable-next-line react-hooks/set-state-in-effect
      setHits([]);
      return;
    }
    let alive = true;
    (async () => {
      const out: SearchHit[] = [];
      try {
        const [runs, leads, tools] = await Promise.all([
          backend.listRuns(),
          backend.listLeads(),
          backend.listTools(),
        ]);
        const lq = q.toLowerCase();
        for (const r of runs) {
          if (`${r.id} ${r.intent} ${r.worker}`.toLowerCase().includes(lq))
            out.push({ kind: "run", id: r.id, title: r.intent.slice(0, 60), sub: `run · ${r.id}`, href: `/runs/${r.id}` });
        }
        for (const l of leads) {
          if (`${l.company_name} ${l.industry}`.toLowerCase().includes(lq))
            out.push({ kind: "lead", id: l.id, title: l.company_name ?? l.id, sub: `prospect · ${l.stage}`, href: `/prospects/${l.id}` });
        }
        for (const t of tools) {
          if (`${t.name} ${t.description}`.toLowerCase().includes(lq))
            out.push({ kind: "tool", id: t.name, title: t.name, sub: "tool", href: `/tools/${encodeURIComponent(t.name)}` });
        }
      } catch {
        /* demo */
      }
      if (alive) setHits(out.slice(0, 8));
    })();
    return () => {
      alive = false;
    };
  }, [q, backend]);

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-hairline-soft bg-surface-0/70 px-4 backdrop-blur">
      <div className="hidden items-center gap-2 md:flex">
        <WorkerMark size={20} />
        <span className="text-sm font-medium text-ink-1">{title}</span>
      </div>

      <div ref={boxRef} className="relative ml-auto w-full max-w-md">
        <button
          onClick={() => setOpen(true)}
          className="group flex w-full items-center gap-2 rounded-md border border-hairline-soft bg-surface-1 px-3 py-1.5 text-sm text-ink-3 transition-colors hover:border-hairline hover:text-ink-2"
          aria-label="Open command palette"
        >
          <Search className="h-4 w-4" />
          <span className="flex-1 text-left">Search runs, evidence, tools…</span>
          <kbd className="mono rounded border border-hairline-soft bg-surface-3 px-1.5 py-0.5 text-[10px] text-ink-3">
            ⌘K
          </kbd>
        </button>

        {open && q ? (
          <div className="absolute left-0 right-0 top-11 z-40 overflow-hidden rounded-md border border-hairline bg-surface-1 shadow-2xl">
            {hits.length === 0 ? (
              <div className="px-3 py-6 text-center text-sm text-ink-3">No matches for “{q}”.</div>
            ) : (
              <ul className="max-h-80 overflow-y-auto py-1">
                {hits.map((h) => (
                  <li key={`${h.kind}-${h.id}`}>
                    <button
                      onClick={() => {
                        router.push(h.href);
                        setLocalOpen(false);
                        setQ("");
                      }}
                      className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left hover:bg-surface-3/60"
                    >
                      <div className="min-w-0">
                        <div className="truncate text-sm text-ink-0">{h.title}</div>
                        <div className="truncate text-xs text-ink-3">{h.sub}</div>
                      </div>
                      <Badge tone="neutral">{h.kind}</Badge>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : null}
      </div>

      <button
        onClick={togglePalette}
        className="grid h-9 w-9 place-items-center rounded-md border border-hairline-soft text-ink-2 transition-colors hover:text-ink-0"
        aria-label="Command palette"
        title="Command palette (⌘K)"
      >
        <Command className="h-4 w-4" />
      </button>

      <button
        onClick={toggle}
        className="grid h-9 w-9 place-items-center rounded-md border border-hairline-soft text-ink-2 transition-colors hover:text-ink-0"
        aria-label="Toggle theme"
        title="Toggle theme"
      >
        {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </button>

      <button
        className="relative grid h-9 w-9 place-items-center rounded-md border border-hairline-soft text-ink-2 transition-colors hover:text-ink-0"
        aria-label="Notifications"
      >
        <Bell className="h-4 w-4" />
        <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-block" />
      </button>
    </header>
  );
}

"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useBackend } from "./backend-provider";

export interface Command {
  id: string;
  label: string;
  hint?: string;
  group: string;
  run: () => void;
  keywords?: string;
}

interface PaletteCtx {
  open: boolean;
  setOpen: (v: boolean) => void;
  toggle: () => void;
}

const Ctx = createContext<PaletteCtx | null>(null);

export function CommandPaletteProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const backend = useBackend();

  const toggle = useCallback(() => setOpen((o) => !o), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        toggle();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggle]);

  // Build the command set from the live backend (routes always exist).
  const go = useCallback(
    (path: string) => {
      setOpen(false);
      router.push(path);
    },
    [router, setOpen],
  );

  const commands: Command[] = [
    { id: "home", group: "Navigate", label: "Go to Mission Control", run: () => go("/") },
    { id: "runs", group: "Navigate", label: "Open Run Explorer", run: () => go("/runs") },
    { id: "prospects", group: "Navigate", label: "Open Prospects", run: () => go("/prospects") },
    { id: "evidence", group: "Navigate", label: "Open Evidence", run: () => go("/evidence") },
    { id: "artifacts", group: "Navigate", label: "Open Artifacts", run: () => go("/artifacts") },
    {
      id: "approvals",
      group: "Navigate",
      label: "Open Approvals",
      run: () => go("/approvals"),
      hint: backend.source === "demo" ? "" : "",
    },
    { id: "policy", group: "Navigate", label: "Open Policy Explorer", run: () => go("/policy") },
    { id: "tools", group: "Navigate", label: "Open Tool Registry", run: () => go("/tools") },
    { id: "audit", group: "Navigate", label: "Open Audit", run: () => go("/audit") },
    { id: "replay", group: "Navigate", label: "Open Replay", run: () => go("/replay") },
    { id: "workers", group: "Navigate", label: "Open Workers", run: () => go("/workers") },
    { id: "settings", group: "Navigate", label: "Open Settings", run: () => go("/settings") },
    {
      id: "theme",
      group: "Action",
      label: "Toggle theme (dark / light)",
      keywords: "dark light appearance",
      run: () => {
        setOpen(false);
        window.dispatchEvent(new CustomEvent("sw-toggle-theme"));
      },
    },
    {
      id: "search-runs",
      group: "Search",
      label: "Search runs…",
      keywords: "filter executions",
      run: () => go("/runs?focus=search"),
    },
  ];

  return (
    <Ctx.Provider value={{ open, setOpen, toggle }}>
      {children}
      {open ? <PaletteShell commands={commands} onClose={() => setOpen(false)} /> : null}
    </Ctx.Provider>
  );
}

function PaletteShell({ commands, onClose }: { commands: Command[]; onClose: () => void }) {
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);

  const filtered = commands.filter((c) => {
    if (!q) return true;
    const s = `${c.label} ${c.group} ${c.keywords ?? ""}`.toLowerCase();
    return s.includes(q.toLowerCase());
  });

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setActive(0);
  }, [q]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActive((a) => Math.min(a + 1, filtered.length - 1));
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setActive((a) => Math.max(a - 1, 0));
      }
      if (e.key === "Enter" && filtered[active]) {
        e.preventDefault();
        filtered[active].run();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [filtered, active, onClose]);

  const groups = Array.from(new Set(filtered.map((c) => c.group)));

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/55 backdrop-blur-sm pt-[12vh]"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
    >
      <div
        className="surface w-full max-w-xl overflow-hidden border border-hairline shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 border-b border-hairline-soft px-4">
          <span className="text-ink-3">⌘K</span>
          <input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Type a command or search…"
            className="w-full bg-transparent py-3.5 text-ink-0 outline-none placeholder:text-ink-3"
            aria-label="Command query"
          />
        </div>
        <div className="max-h-[52vh] overflow-y-auto p-1.5">
          {filtered.length === 0 ? (
            <div className="px-3 py-8 text-center text-sm text-ink-3">No matching commands.</div>
          ) : (
            groups.map((g) => (
              <div key={g} className="mb-1">
                <div className="px-3 pb-1 pt-2 text-[10px] font-medium uppercase tracking-[0.18em] text-ink-4">
                  {g}
                </div>
                {filtered
                  .filter((c) => c.group === g)
                  .map((c) => {
                    const idx = filtered.indexOf(c);
                    return (
                      <button
                        key={c.id}
                        onMouseEnter={() => setActive(idx)}
                        onClick={() => c.run()}
                        className={`flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm ${
                          idx === active ? "bg-accent/10 text-ink-0" : "text-ink-1 hover:bg-surface-3/60"
                        }`}
                      >
                        <span>{c.label}</span>
                        {c.hint ? <span className="text-xs text-ink-3">{c.hint}</span> : null}
                      </button>
                    );
                  })}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

export function useCommandPalette() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useCommandPalette outside provider");
  return c;
}

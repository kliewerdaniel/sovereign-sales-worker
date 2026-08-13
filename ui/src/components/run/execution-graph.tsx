"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/cn";
import { TONE_CLASS } from "@/lib/domain";
import { StageNode } from "@/lib/run-graph";

export interface GraphSelection {
  key: string;
  refs: string[];
}

/** Vertical lifecycle spine: REQUEST → … → AUDIT. Each node communicates state,
 *  lights up on hover/selection, and reveals its attached record refs. */
export function ExecutionGraph({
  nodes,
  selected,
  onSelect,
  compact = false,
}: {
  nodes: StageNode[];
  selected: string | null;
  onSelect: (s: GraphSelection) => void;
  compact?: boolean;
}) {
  return (
    <div className="flex flex-col">
      {nodes.map((n, i) => (
        <GraphRow
          key={n.key}
          node={n}
          index={i}
          isLast={i === nodes.length - 1}
          active={selected === n.key}
          compact={compact}
          onSelect={() => onSelect({ key: n.key, refs: n.refs })}
        />
      ))}
    </div>
  );
}

function GraphRow({
  node,
  index,
  isLast,
  active,
  compact,
  onSelect,
}: {
  node: StageNode;
  index: number;
  isLast: boolean;
  active: boolean;
  compact: boolean;
  onSelect: () => void;
}) {
  const c = TONE_CLASS[node.status];
  return (
    <div className="flex gap-3">
      {/* rail */}
      <div className="flex w-9 shrink-0 flex-col items-center">
        <button
          onClick={onSelect}
          aria-label={`${node.label} stage`}
          aria-pressed={active}
          className={cn(
            "grid h-9 w-9 place-items-center rounded-full border text-[11px] font-semibold transition-all",
            active ? "scale-105 ring-2 ring-accent/40" : "hover:scale-105",
            c.text,
            c.bg,
            c.border,
          )}
        >
          {index + 1}
        </button>
        {!isLast ? (
          <div className={cn("mt-1 w-px flex-1", active ? "bg-accent/40" : "bg-hairline-soft")} aria-hidden />
        ) : (
          <div className="mt-1 w-px flex-1 bg-transparent" />
        )}
      </div>

      {/* body */}
      <motion.button
        onClick={onSelect}
        initial={false}
        animate={{ borderColor: active ? "var(--color-accent)" : "var(--color-hairline-soft)" }}
        className={cn(
          "group mb-2 flex-1 rounded-md border bg-surface-1 px-3.5 py-2.5 text-left transition-colors",
          active ? "bg-surface-2" : "hover:bg-surface-2/60",
          compact && "py-2",
        )}
      >
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span className={cn("text-sm font-semibold", c.text)}>{node.label}</span>
            <span className={cn("rounded-full border px-1.5 py-0.5 text-[10px]", c.text, c.border, c.bg)}>
              {node.statusLabel}
            </span>
          </div>
          {node.count != null ? (
            <span className="mono text-xs text-ink-3">{node.count}</span>
          ) : null}
        </div>
        {!compact ? (
          <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-ink-3">{node.detail}</p>
        ) : null}
      </motion.button>
    </div>
  );
}

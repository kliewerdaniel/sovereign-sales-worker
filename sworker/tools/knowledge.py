"""Knowledge tools — retrieval over compiled company memory (Atlas)."""

from __future__ import annotations

import json
from typing import Any, Dict

from .. import knowledge as K
from ..models import RiskLevel
from .base import Tool, ToolContext, ToolResult, truncate


class KnowledgeSearch(Tool):
    name = "knowledge.search"
    description = (
        "Search compiled company knowledge. Returns claims with confidence, source "
        "documents and contradiction ids. Degrades to labelled grep if the knowledge "
        "compiler is unavailable."
    )
    risk = RiskLevel.READ
    input_schema = {
        "type": "object",
        "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "default": 8}},
        "required": ["query"],
    }

    def run(self, ctx: ToolContext, args: Dict[str, Any]) -> ToolResult:
        import os

        atlas_dir = os.path.join(ctx.workspace, ".state", "atlas")
        limit = int(args.get("limit", 8))
        claims = K.search_claims(atlas_dir, args["query"], limit=limit)
        if claims:
            lines = []
            evidence = []
            for c in claims:
                src = ", ".join(s.get("title") or s.get("path", "") for s in c["sources"]) or "?"
                flag = " [CONTESTED]" if c["contradiction_ids"] else ""
                lines.append(
                    f"- {c['text']} (confidence={c['confidence']}, source={src}){flag}"
                )
                evidence.append(
                    {
                        "source_ref": c["claim_id"],
                        "excerpt": f"{c['text']} <- {src}",
                        "atlas_claim": True,
                    }
                )
            body, trunc = truncate("\n".join(lines), ctx.max_output)
            return ToolResult(
                True,
                output=body,
                truncated=trunc,
                data={"claims": claims, "mode": "compiled", "count": len(claims)},
                evidence=evidence,
            )

        roots = [os.path.join(ctx.workspace, "company")]
        hits = K.grep_knowledge(roots, args["query"], limit=limit)
        if not hits:
            return ToolResult(
                True,
                output="(no company knowledge matched this query)",
                data={"claims": [], "mode": "empty", "count": 0},
            )
        body = "\n".join(f"{h['path']}:{h['line']}: {h['text']}" for h in hits)
        return ToolResult(
            True,
            output="[degraded: raw document grep, knowledge not compiled]\n" + body,
            data={"hits": hits, "mode": "grep", "count": len(hits)},
            evidence=[
                {"source_ref": f"{h['path']}:{h['line']}", "excerpt": h["text"]} for h in hits
            ],
        )


class KnowledgeExplain(Tool):
    name = "knowledge.explain"
    description = "Explain why a compiled claim is believed: evidence, sources, lifecycle."
    risk = RiskLevel.READ
    input_schema = {
        "type": "object",
        "properties": {"claim_id": {"type": "string"}},
        "required": ["claim_id"],
    }

    def run(self, ctx: ToolContext, args: Dict[str, Any]) -> ToolResult:
        import os

        atlas_dir = os.path.join(ctx.workspace, ".state", "atlas")
        entry = K.explain_claim(atlas_dir, args["claim_id"])
        if not entry:
            return ToolResult(False, error=f"no compiled claim {args['claim_id']!r}")
        try:
            from hermes_atlas.explain import format_human  # type: ignore

            body = format_human(entry)
        except Exception:
            body = json.dumps(entry, indent=2, sort_keys=True, default=str)
        body, trunc = truncate(body, ctx.max_output)
        return ToolResult(
            True,
            output=body,
            truncated=trunc,
            data={"claim": entry},
            evidence=[{"source_ref": args["claim_id"], "excerpt": body[:400]}],
        )


TOOLS = [KnowledgeSearch(), KnowledgeExplain()]

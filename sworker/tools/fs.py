"""Filesystem tools. Every path passes through ToolContext.resolve()."""

from __future__ import annotations

import fnmatch
import os
import re
from typing import Any, Dict

from ..models import RiskLevel
from .base import Tool, ToolContext, ToolError, ToolResult, truncate


class ReadFile(Tool):
    name = "fs.read"
    description = "Read a UTF-8 text file inside the worker's filesystem boundary."
    risk = RiskLevel.READ
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path, relative to the workspace."},
            "max_bytes": {"type": "integer", "default": 200000},
        },
        "required": ["path"],
    }

    def run(self, ctx: ToolContext, args: Dict[str, Any]) -> ToolResult:
        p = ctx.resolve(args["path"], must_exist=True)
        if os.path.isdir(p):
            return ToolResult(False, error=f"{args['path']} is a directory")
        with open(p, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read(int(args.get("max_bytes", 200000)))
        body, trunc = truncate(text, ctx.max_output)
        return ToolResult(
            True,
            output=body,
            truncated=trunc,
            data={"path": p, "bytes": len(text)},
            evidence=[{"source_ref": p, "excerpt": text[:400]}],
        )


class WriteFile(Tool):
    name = "fs.write"
    description = "Create or overwrite a text file inside the worker's boundary."
    risk = RiskLevel.REVERSIBLE
    reversible = True
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
    }

    def summarize(self, args: Dict[str, Any]) -> str:
        return f"write {len(args.get('content', ''))} bytes to {args.get('path')}"

    def run(self, ctx: ToolContext, args: Dict[str, Any]) -> ToolResult:
        p = ctx.resolve(args["path"])
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        existed = os.path.exists(p)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(args["content"])
        return ToolResult(
            True,
            output=f"{'overwrote' if existed else 'wrote'} {p} ({len(args['content'])} bytes)",
            data={"path": p, "bytes": len(args["content"]), "overwrote": existed},
            artifacts=[p],
        )


class DeleteFile(Tool):
    name = "fs.delete"
    description = "Delete a file. Irreversible."
    risk = RiskLevel.DESTRUCTIVE
    reversible = False
    requires_approval = True
    input_schema = {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}

    def summarize(self, args: Dict[str, Any]) -> str:
        return f"DELETE file {args.get('path')} (irreversible)"

    def run(self, ctx: ToolContext, args: Dict[str, Any]) -> ToolResult:
        p = ctx.resolve(args["path"], must_exist=True)
        if os.path.isdir(p):
            return ToolResult(False, error="refusing to delete a directory")
        size = os.path.getsize(p)
        os.remove(p)
        return ToolResult(True, output=f"deleted {p} ({size} bytes)", data={"path": p})


class ListDir(Tool):
    name = "fs.list"
    description = "List directory entries (one level) inside the worker's boundary."
    risk = RiskLevel.READ
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "default": "."},
            "pattern": {"type": "string", "default": "*"},
        },
    }

    def run(self, ctx: ToolContext, args: Dict[str, Any]) -> ToolResult:
        p = ctx.resolve(args.get("path", "."), must_exist=True)
        if not os.path.isdir(p):
            return ToolResult(False, error=f"{args.get('path')} is not a directory")
        pat = args.get("pattern", "*")
        entries = []
        for name in sorted(os.listdir(p)):
            if name.startswith("."):
                continue
            if not fnmatch.fnmatch(name, pat):
                continue
            full = os.path.join(p, name)
            entries.append(
                {
                    "name": name,
                    "dir": os.path.isdir(full),
                    "bytes": 0 if os.path.isdir(full) else os.path.getsize(full),
                }
            )
        listing = "\n".join(
            ("%s/" % e["name"]) if e["dir"] else f"{e['name']}  {e['bytes']}b" for e in entries
        )
        return ToolResult(
            True,
            output=listing or "(empty)",
            data={"path": p, "entries": entries, "count": len(entries)},
            evidence=[{"source_ref": p, "excerpt": listing[:400]}],
        )


class SearchFiles(Tool):
    name = "fs.search"
    description = "Regex-search file contents under a directory. Returns path:line matches."
    risk = RiskLevel.READ
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string"},
            "path": {"type": "string", "default": "."},
            "glob": {"type": "string", "default": "*"},
            "limit": {"type": "integer", "default": 50},
        },
        "required": ["pattern"],
    }

    def run(self, ctx: ToolContext, args: Dict[str, Any]) -> ToolResult:
        root = ctx.resolve(args.get("path", "."), must_exist=True)
        try:
            rx = re.compile(args["pattern"], re.IGNORECASE)
        except re.error as exc:
            raise ToolError(f"invalid regex: {exc}") from exc
        limit = int(args.get("limit", 50))
        glob = args.get("glob", "*")
        hits = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in sorted(dirnames) if not d.startswith(".")]
            for fn in sorted(filenames):
                if fn.startswith(".") or not fnmatch.fnmatch(fn, glob):
                    continue
                full = os.path.join(dirpath, fn)
                try:
                    with open(full, "r", encoding="utf-8", errors="replace") as fh:
                        for i, line in enumerate(fh, 1):
                            if rx.search(line):
                                hits.append(
                                    {
                                        "path": full,
                                        "line": i,
                                        "text": line.rstrip()[:300],
                                    }
                                )
                                if len(hits) >= limit:
                                    break
                except OSError:
                    continue
                if len(hits) >= limit:
                    break
            if len(hits) >= limit:
                break
        rendered = "\n".join(f"{h['path']}:{h['line']}: {h['text']}" for h in hits)
        return ToolResult(
            True,
            output=rendered or "(no matches)",
            data={"matches": hits, "count": len(hits)},
            evidence=[
                {"source_ref": f"{h['path']}:{h['line']}", "excerpt": h["text"]} for h in hits[:10]
            ],
        )


TOOLS = [ReadFile(), WriteFile(), DeleteFile(), ListDir(), SearchFiles()]

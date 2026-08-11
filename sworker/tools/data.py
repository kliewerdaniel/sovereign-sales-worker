"""Deterministic tabular analysis.

This is the load-bearing evidence tool. Revenue numbers must come from summing
an actual CSV column with stdlib arithmetic — never from a language model
reading numbers out of a document. Every result carries the row count and the
file checksum so ``verify.py`` can independently recompute it.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import statistics
from typing import Any, Dict, List, Optional

from ..models import RiskLevel
from .base import Tool, ToolContext, ToolError, ToolResult


def read_csv(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _num(v: Any) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip().replace(",", "").replace("$", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _matches(row: Dict[str, str], where: Dict[str, Any]) -> bool:
    for key, cond in where.items():
        val = row.get(key)
        if isinstance(cond, dict):
            n = _num(val)
            for op, target in cond.items():
                t = _num(target)
                if op in (">", ">=", "<", "<=") and (n is None or t is None):
                    return False
                if op == ">" and not n > t:      # type: ignore[operator]
                    return False
                if op == ">=" and not n >= t:    # type: ignore[operator]
                    return False
                if op == "<" and not n < t:      # type: ignore[operator]
                    return False
                if op == "<=" and not n <= t:    # type: ignore[operator]
                    return False
                if op == "!=" and str(val) == str(target):
                    return False
                if op == "==" and str(val) != str(target):
                    return False
                if op == "contains" and str(target).lower() not in str(val or "").lower():
                    return False
                if op == "gte_str" and str(val) < str(target):
                    return False
                if op == "lte_str" and str(val) > str(target):
                    return False
        else:
            if str(val) != str(cond):
                return False
    return True


class CsvInspect(Tool):
    name = "data.inspect"
    description = "Report a CSV's columns, row count, checksum and first rows."
    risk = RiskLevel.READ
    input_schema = {
        "type": "object",
        "properties": {"path": {"type": "string"}, "rows": {"type": "integer", "default": 5}},
        "required": ["path"],
    }

    def run(self, ctx: ToolContext, args: Dict[str, Any]) -> ToolResult:
        p = ctx.resolve(args["path"], must_exist=True)
        rows = read_csv(p)
        cols = list(rows[0].keys()) if rows else []
        head = rows[: int(args.get("rows", 5))]
        digest = file_sha256(p)
        body = (
            f"{os.path.basename(p)}: {len(rows)} rows, columns: {', '.join(cols)}\n"
            + "\n".join(json.dumps(r, sort_keys=True) for r in head)
        )
        return ToolResult(
            True,
            output=body,
            data={"path": p, "rows": len(rows), "columns": cols, "sha256": digest, "head": head},
            evidence=[{"source_ref": f"{p}#sha256:{digest[:12]}", "excerpt": body[:400]}],
        )


class CsvQuery(Tool):
    name = "data.query"
    description = (
        "Filter, group and aggregate a CSV deterministically. "
        "where: {col: value} or {col: {'>=': 10}} / {'contains': 'x'} / "
        "{'gte_str': '2026-01-01'}. agg: sum|mean|min|max|count over `value_column`, "
        "optionally grouped by `group_by`."
    )
    risk = RiskLevel.READ
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "where": {"type": "object", "default": {}},
            "group_by": {"type": "string", "default": ""},
            "value_column": {"type": "string", "default": ""},
            "agg": {
                "type": "string",
                "default": "sum",
                "enum": ["sum", "mean", "min", "max", "count"],
            },
            "sort_desc": {"type": "boolean", "default": True},
            "limit": {"type": "integer", "default": 20},
        },
        "required": ["path"],
    }

    def summarize(self, args):
        return (
            f"{args.get('agg','sum')}({args.get('value_column') or 'rows'}) over "
            f"{os.path.basename(str(args.get('path')))} where={args.get('where') or '{}'}"
        )

    def run(self, ctx: ToolContext, args: Dict[str, Any]) -> ToolResult:
        p = ctx.resolve(args["path"], must_exist=True)
        rows = read_csv(p)
        where = args.get("where") or {}
        if rows and where:
            unknown = set(where) - set(rows[0].keys())
            if unknown:
                raise ToolError(
                    f"data.query: column(s) {sorted(unknown)} not in {os.path.basename(p)} "
                    f"(have: {list(rows[0].keys())})"
                )
        selected = [r for r in rows if _matches(r, where)]
        agg = args.get("agg", "sum")
        vcol = args.get("value_column") or ""
        gcol = args.get("group_by") or ""
        if agg != "count" and not vcol:
            raise ToolError("data.query: value_column is required unless agg='count'")
        if vcol and rows and vcol not in rows[0]:
            raise ToolError(f"data.query: value_column {vcol!r} not in {os.path.basename(p)}")

        def reduce(vals: List[float]) -> float:
            if agg == "count":
                return float(len(vals))
            if not vals:
                return 0.0
            if agg == "sum":
                return sum(vals)
            if agg == "mean":
                return statistics.fmean(vals)
            if agg == "min":
                return min(vals)
            return max(vals)

        digest = file_sha256(p)
        if gcol:
            buckets: Dict[str, List[float]] = {}
            counts: Dict[str, int] = {}
            for r in selected:
                key = str(r.get(gcol, ""))
                counts[key] = counts.get(key, 0) + 1
                if vcol:
                    n = _num(r.get(vcol))
                    if n is not None:
                        buckets.setdefault(key, []).append(n)
                else:
                    buckets.setdefault(key, [])
            groups = [
                {"key": k, "value": round(reduce(buckets.get(k, [])), 6), "rows": counts[k]}
                for k in counts
            ]
            groups.sort(key=lambda g: g["value"], reverse=bool(args.get("sort_desc", True)))
            groups = groups[: int(args.get("limit", 20))]
            body = "\n".join(f"{g['key']}: {g['value']} ({g['rows']} rows)" for g in groups)
            data = {
                "path": p,
                "sha256": digest,
                "matched_rows": len(selected),
                "total_rows": len(rows),
                "agg": agg,
                "value_column": vcol,
                "group_by": gcol,
                "groups": groups,
            }
        else:
            vals = [n for n in (_num(r.get(vcol)) for r in selected) if n is not None] if vcol else []
            value = round(reduce(vals), 6)
            body = f"{agg}({vcol or 'rows'}) = {value} over {len(selected)}/{len(rows)} rows"
            data = {
                "path": p,
                "sha256": digest,
                "matched_rows": len(selected),
                "total_rows": len(rows),
                "agg": agg,
                "value_column": vcol,
                "value": value,
            }
        return ToolResult(
            True,
            output=body,
            data=data,
            evidence=[
                {
                    "source_ref": f"{p}#sha256:{digest[:12]}",
                    "excerpt": f"{self.summarize(args)} -> {body[:300]}",
                }
            ],
        )


TOOLS = [CsvInspect(), CsvQuery()]

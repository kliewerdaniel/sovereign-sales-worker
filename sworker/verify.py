"""Deterministic verification.

A Verification is a CHECK THAT RE-DERIVES A NUMBER FROM SOURCE DATA, written in
Python, with no model in the loop. If the recomputation disagrees with the
claim, the claim is marked REFUTED and the run degrades — it does not quietly
keep the nicer number.

Checks are declared as small dicts so procedures (YAML) can carry them:

    {"check": "recompute_sum", "path": "...", "value_column": "revenue",
     "where": {...}, "expect": 12345.6, "tolerance": 0.01}
"""

from __future__ import annotations

import math
import os
from typing import Any, Callable, Dict, List, Optional

from dataclasses import dataclass, field

from .models import VerificationOutcome
from .tools.data import _matches, _num, file_sha256, read_csv


@dataclass
class CheckResult:
    """Pure result of a deterministic check.

    Kept separate from the persisted ``Verification`` record so checks stay pure
    functions the tests can call without a store or a run.
    """

    check: str
    status: VerificationOutcome
    detail: str = ""
    expected: Any = None
    actual: Any = None
    source_ref: str = ""

    @property
    def passed(self) -> bool:
        return self.status is VerificationOutcome.PASS


CheckFn = Callable[[Dict[str, Any], str], "CheckResult"]
_CHECKS: Dict[str, CheckFn] = {}


def check(name: str):
    def deco(fn: CheckFn) -> CheckFn:
        _CHECKS[name] = fn
        return fn

    return deco


def available_checks() -> List[str]:
    return sorted(_CHECKS)


def run_check(spec: Dict[str, Any], workspace: str) -> CheckResult:
    name = spec.get("check", "")
    fn = _CHECKS.get(name)
    if fn is None:
        return CheckResult(
            check=name or "(unnamed)",
            status=VerificationOutcome.UNVERIFIABLE,
            detail=f"unknown check {name!r}; available: {available_checks()}",
        )
    try:
        return fn(spec, workspace)
    except Exception as exc:
        return CheckResult(
            check=name,
            status=VerificationOutcome.UNVERIFIABLE,
            detail=f"{type(exc).__name__}: {exc}",
        )


def _resolve(workspace: str, path: str) -> str:
    p = os.path.realpath(os.path.join(workspace, os.path.expanduser(path)))
    root = os.path.realpath(workspace)
    if not (p == root or p.startswith(root + os.sep)):
        raise ValueError(f"verification path {path!r} escapes the workspace")
    return p


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------


@check("recompute_sum")
def _recompute_sum(spec: Dict[str, Any], workspace: str) -> Verification:
    """Independently re-sum a CSV column and compare with the claimed total."""
    path = _resolve(workspace, spec["path"])
    rows = read_csv(path)
    where = spec.get("where") or {}
    col = spec["value_column"]
    vals = [
        n
        for n in (_num(r.get(col)) for r in rows if _matches(r, where))
        if n is not None
    ]
    actual = round(sum(vals), 6)
    expect = _num(spec.get("expect"))
    tol = float(spec.get("tolerance", 0.01))
    if expect is None:
        return CheckResult(
            check="recompute_sum",
            status=VerificationOutcome.UNVERIFIABLE,
            detail=f"recomputed {col} = {actual} over {len(vals)} rows, but no expected value given",
            expected=None,
            actual=actual,
            source_ref=f"{path}#sha256:{file_sha256(path)[:12]}",
        )
    ok = math.isclose(actual, expect, rel_tol=0, abs_tol=max(tol, abs(expect) * 0.001))
    return CheckResult(
        check="recompute_sum",
        status=VerificationOutcome.PASS if ok else VerificationOutcome.FAIL,
        detail=(
            f"independently summed {col} over {len(vals)} rows of "
            f"{os.path.basename(path)}: {actual} vs claimed {expect}"
            + ("" if ok else f" — MISMATCH (tolerance {tol})")
        ),
        expected=expect,
        actual=actual,
        source_ref=f"{path}#sha256:{file_sha256(path)[:12]}",
    )


@check("recompute_delta_pct")
def _recompute_delta(spec: Dict[str, Any], workspace: str) -> Verification:
    """Re-derive a percentage change between two filtered windows of one CSV."""
    path = _resolve(workspace, spec["path"])
    rows = read_csv(path)
    col = spec["value_column"]

    def total(where: Dict[str, Any]) -> float:
        vals = [
            n for n in (_num(r.get(col)) for r in rows if _matches(r, where)) if n is not None
        ]
        return round(sum(vals), 6)

    cur = total(spec.get("current") or {})
    prev = total(spec.get("previous") or {})
    if prev == 0:
        return CheckResult(
            check="recompute_delta_pct",
            status=VerificationOutcome.UNVERIFIABLE,
            detail=f"previous period total is 0; percentage change undefined (current={cur})",
            actual=cur,
            source_ref=path,
        )
    actual = round((cur - prev) / prev * 100.0, 4)
    expect = _num(spec.get("expect"))
    if expect is None:
        return CheckResult(
            check="recompute_delta_pct",
            status=VerificationOutcome.UNVERIFIABLE,
            detail=f"recomputed change = {actual}% (current {cur} vs previous {prev})",
            actual=actual,
            source_ref=path,
        )
    tol = float(spec.get("tolerance", 0.5))
    ok = abs(actual - expect) <= tol
    return CheckResult(
        check="recompute_delta_pct",
        status=VerificationOutcome.PASS if ok else VerificationOutcome.FAIL,
        detail=(
            f"recomputed {col} change: {actual}% (current {cur} vs previous {prev}); "
            f"claimed {expect}%" + ("" if ok else f" — MISMATCH (tolerance {tol}pp)")
        ),
        expected=expect,
        actual=actual,
        source_ref=f"{path}#sha256:{file_sha256(path)[:12]}",
    )


@check("row_count")
def _row_count(spec: Dict[str, Any], workspace: str) -> Verification:
    path = _resolve(workspace, spec["path"])
    rows = read_csv(path)
    matched = [r for r in rows if _matches(r, spec.get("where") or {})]
    actual = float(len(matched))
    expect = _num(spec.get("expect"))
    if expect is None:
        return CheckResult(
            check="row_count",
            status=VerificationOutcome.UNVERIFIABLE,
            detail=f"{len(matched)} rows matched",
            actual=actual,
            source_ref=path,
        )
    ok = actual == expect
    return CheckResult(
        check="row_count",
        status=VerificationOutcome.PASS if ok else VerificationOutcome.FAIL,
        detail=f"{len(matched)} rows matched, expected {int(expect)}",
        expected=expect,
        actual=actual,
        source_ref=path,
    )


@check("file_exists")
def _file_exists(spec: Dict[str, Any], workspace: str) -> Verification:
    path = _resolve(workspace, spec["path"])
    ok = os.path.isfile(path)
    size = os.path.getsize(path) if ok else 0
    min_bytes = int(spec.get("min_bytes", 1))
    passed = ok and size >= min_bytes
    return CheckResult(
        check="file_exists",
        status=VerificationOutcome.PASS if passed else VerificationOutcome.FAIL,
        detail=(
            f"{os.path.basename(path)} exists ({size} bytes)"
            if ok
            else f"{spec['path']} does not exist"
        )
        + ("" if passed else f" — required at least {min_bytes} bytes"),
        expected=float(min_bytes),
        actual=float(size),
        source_ref=path,
    )


@check("artifact_contains_evidence")
def _artifact_contains_evidence(spec: Dict[str, Any], workspace: str) -> Verification:
    """A report that states numbers must also cite where they came from."""
    path = _resolve(workspace, spec["path"])
    if not os.path.isfile(path):
        return CheckResult(
            check="artifact_contains_evidence",
            status=VerificationOutcome.FAIL,
            detail=f"artifact {spec['path']} does not exist",
            source_ref=path,
        )
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    markers = spec.get("markers") or ["Evidence:", "evidence"]
    found = sum(1 for m in markers if m.lower() in text.lower())
    minimum = int(spec.get("min_mentions", 1))
    ok = found >= minimum
    return CheckResult(
        check="artifact_contains_evidence",
        status=VerificationOutcome.PASS if ok else VerificationOutcome.FAIL,
        detail=(
            f"{os.path.basename(path)} references evidence "
            f"({found}/{len(markers)} markers found, need {minimum})"
        ),
        expected=float(minimum),
        actual=float(found),
        source_ref=path,
    )


@check("totals_match_source")
def _totals_match_source(spec: Dict[str, Any], workspace: str) -> Verification:
    """Every number the report claims for `value_column` must equal the CSV sum."""
    src = _resolve(workspace, spec["path"])
    rows = read_csv(src)
    col = spec["value_column"]
    vals = [
        n
        for n in (_num(r.get(col)) for r in rows if _matches(r, spec.get("where") or {}))
        if n is not None
    ]
    actual = round(sum(vals), 2)
    report = _resolve(workspace, spec["artifact"])
    if not os.path.isfile(report):
        return CheckResult(
            check="totals_match_source",
            status=VerificationOutcome.FAIL,
            detail=f"artifact {spec['artifact']} not found; cannot compare totals",
            actual=actual,
            source_ref=src,
        )
    with open(report, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    needle = f"{actual:,.2f}"
    alt = f"{actual:.2f}"
    ok = needle in text or alt in text or f"{int(actual):,}" in text
    return CheckResult(
        check="totals_match_source",
        status=VerificationOutcome.PASS if ok else VerificationOutcome.FAIL,
        detail=(
            f"source total for {col} is {actual}; artifact "
            f"{'cites' if ok else 'DOES NOT cite'} that figure"
        ),
        expected=actual,
        actual=actual if ok else None,
        source_ref=f"{src}#sha256:{file_sha256(src)[:12]}",
    )

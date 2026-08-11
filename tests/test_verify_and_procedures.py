"""Unit tests for deterministic verification, scheduler, and procedural memory."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from sworker.config import Workspace
from sworker.store import WorkerStore
from sworker.verify import run_check, available_checks, VerificationOutcome
from sworker.scheduler import parse_cron, next_fire
from sworker.procedures import (
    learn_from_run,
    save_procedure,
    list_procedures,
    load_procedure,
    substitute,
    procedure_steps,
)
from sworker.models import RunStatus


SALES_CSV = """region,quarter,revenue,orders
North,Q1,42000,1320
North,Q2,51000,1480
South,Q1,31000,980
South,Q2,35500,1100
Online,Q1,88000,4200
Online,Q2,102000,5100
"""

WORKER_YAML = """name: acme-analyst
role: Acme Coffee business analyst
instructions: |
  Compute figures from the CSVs with data.query.
tools: [fs.list, fs.read, fs.write, data.query, data.inspect, knowledge.search]
policy:
  read: auto
  reversible: auto
  external: approve
  financial: approve
  destructive: approve
fs_roots: [company]
"""


@pytest.fixture()
def ws(tmp_path):
    home = tmp_path / "acme"
    (home / "company").mkdir(parents=True)
    (home / "company" / "sales.csv").write_text(SALES_CSV)
    (home / "workers").mkdir(parents=True)
    (home / "workers" / "acme-analyst.yaml").write_text(WORKER_YAML)
    os.environ["SWORKER_HOME"] = str(home)
    w = Workspace(str(home))
    w.ensure()
    return w


# ---------------------------------------------------------------------------
# verification
# ---------------------------------------------------------------------------


def test_available_checks_nonempty():
    checks = available_checks()
    assert "recompute_sum" in checks
    assert "recompute_delta_pct" in checks
    assert "row_count" in checks


def test_recompute_sum_pass(ws):
    spec = {
        "check": "recompute_sum",
        "path": "company/sales.csv",
        "value_column": "revenue",
        "where": {"quarter": "Q2"},
        "expect": 188500.0,
    }
    res = run_check(spec, ws.root)
    assert res.status is VerificationOutcome.PASS, res.detail
    assert res.actual == 188500.0


def test_recompute_sum_fail_on_wrong_expectation(ws):
    spec = {
        "check": "recompute_sum",
        "path": "company/sales.csv",
        "value_column": "revenue",
        "where": {"quarter": "Q2"},
        "expect": 1.0,
    }
    res = run_check(spec, ws.root)
    assert res.status is VerificationOutcome.FAIL, res.detail


def test_recompute_sum_unverifiable_without_expect(ws):
    spec = {
        "check": "recompute_sum",
        "path": "company/sales.csv",
        "value_column": "revenue",
    }
    res = run_check(spec, ws.root)
    assert res.status is VerificationOutcome.UNVERIFIABLE
    assert res.actual is not None


def test_unknown_check_unverifiable(ws):
    res = run_check({"check": "nope", "path": "x"}, str(ws))
    assert res.status is VerificationOutcome.UNVERIFIABLE


def test_recompute_delta_pct(ws):
    spec = {
        "check": "recompute_delta_pct",
        "path": "company/sales.csv",
        "value_column": "revenue",
        "current": {"quarter": "Q2"},
        "previous": {"quarter": "Q1"},
        "expect": 16.977,  # (188500-161000)/161000*100
    }
    res = run_check(spec, ws.root)
    assert res.status is VerificationOutcome.PASS, res.detail


def test_path_escaping_blocked(ws):
    spec = {"check": "recompute_sum", "path": "../etc/passwd", "value_column": "x"}
    res = run_check(spec, ws.root)
    assert res.status is VerificationOutcome.UNVERIFIABLE


# ---------------------------------------------------------------------------
# scheduler
# ---------------------------------------------------------------------------


def test_parse_cron_alias():
    parsed = parse_cron("@daily")
    assert parsed["minute"] == [0]
    assert parsed["hour"] == [0]


def test_next_fire_daily():
    after = time.mktime(time.strptime("2026-01-01 12:00:00", "%Y-%m-%d %H:%M:%S"))
    nxt = next_fire("@daily", after=after)
    assert time.strftime("%Y-%m-%d %H:%M", time.localtime(nxt)) == "2026-01-02 00:00"


def test_next_fire_weekdays():
    # Friday 2026-01-02 09:30 -> next weekday (Mon) 09:00
    after = time.mktime(time.strptime("2026-01-02 09:30:00", "%Y-%m-%d %H:%M:%S"))
    nxt = next_fire("0 9 * * 1-5", after=after)
    s = time.strftime("%Y-%m-%d %H:%M", time.localtime(nxt))
    assert s == "2026-01-05 09:00", s


def test_next_fire_every_15_min():
    after = time.mktime(time.strptime("2026-01-01 10:00:00", "%Y-%m-%d %H:%M:%S"))
    nxt = next_fire("*/15 * * * *", after=after)
    assert time.strftime("%H:%M", time.localtime(nxt)) == "10:15"


# ---------------------------------------------------------------------------
# procedural memory
# ---------------------------------------------------------------------------


def test_substitute_placeholders():
    assert substitute("sum {{value_column}}", {"value_column": "revenue"}) == "sum revenue"
    assert substitute({"path": "{{file}}", "agg": "sum"}, {"file": "a.csv"}) == {
        "path": "a.csv",
        "agg": "sum",
    }


def test_learn_from_run_generalizes_inputs(ws):
    from sworker.engine import WorkerEngine
    from sworker.config import get_worker
    from sworker.inference import NullInference
    from sworker.tools import build_registry

    worker = get_worker("acme-analyst", ws)
    store = WorkerStore(ws.state_dir)
    engine = WorkerEngine(
        worker, store, inference=NullInference(), registry=build_registry()
    )
    result = engine.run("Q2 revenue total?", inputs={"quarter": "Q2"})
    body = learn_from_run(
        store, result.run.id, "q2_total", inputs={"quarter": "Q2"}
    )
    save_procedure(worker, "q2_total", body)
    procs = {p["name"]: p for p in list_procedures(worker)}
    assert "q2_total" in procs
    # The learned procedure must generalize the literal Q2 back to a placeholder.
    assert "{{quarter}}" in body, body
    steps = procedure_steps(procs["q2_total"], {"quarter": "Q2"})
    # Only actually-executed data/fs actions survive into the procedure.
    assert any(s.get("tool") == "data.query" for s in steps)

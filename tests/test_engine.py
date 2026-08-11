"""End-to-end tests for the Sovereign AI Worker platform.

Run with:  env -u PYTHONPATH -u PYTHONHOME /opt/homebrew/bin/python3.14 -m pytest tests/

These are real integration tests — they build a temp workspace, seed CSV data,
run the engine without a language model (deterministic fallback), and assert on
the persisted run/evidence/artifact records. No mocks, no cloud.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

from sworker.config import Workspace, WorkerConfig, default_workspace
from sworker.store import WorkerStore
from sworker.engine import WorkerEngine
from sworker.inference import NullInference
from sworker.tools import build_registry


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
  Compute figures from the CSVs with data.query; never state a number you did
  not derive. Write a markdown report that cites source totals.
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
    home.mkdir()
    (home / "company").mkdir()
    (home / "company" / "sales.csv").write_text(SALES_CSV)
    (home / "workers").mkdir()
    (home / "workers" / "acme-analyst.yaml").write_text(WORKER_YAML)
    os.environ["SWORKER_HOME"] = str(home)
    w = Workspace(str(home))
    w.ensure()
    return w


def make_engine(ws):
    from sworker.config import get_worker

    worker = get_worker("acme-analyst", ws)
    store = WorkerStore(ws.state_dir)
    registry = build_registry()
    return WorkerEngine(worker, store, inference=NullInference(), registry=registry)


def test_init_creates_workspace(ws):
    assert Path(ws.company_dir).is_dir()
    assert Path(ws.workers_dir).is_dir()
    assert Path(ws.state_dir).is_dir()


def test_run_q2_revenue_success(ws):
    engine = make_engine(ws)
    result = engine.run("What was total Q2 revenue?")
    assert result.status.value == "SUCCESS", result.summary
    # Q2 = 51000 + 35500 + 102000 = 188500
    assert "188,500" in result.summary or "188500" in result.summary, result.summary
    assert len(result.artifacts) >= 1


def test_run_q2_by_channel_grouping(ws):
    engine = make_engine(ws)
    result = engine.run("Q2 revenue by channel?")
    assert result.status.value == "SUCCESS"
    # Online leads at 102000
    text = result.run.summary
    assert "102,000" in text or "102000" in text, text


def test_run_derives_and_passes_verifications(ws):
    """Fallback runs must auto-derive recompute_sum checks and pass them.

    This is the product's core promise: every number the run states is also
    independently re-derived from the source CSV before the run is final.
    """
    engine = make_engine(ws)
    result = engine.run("What was total Q2 revenue?")
    assert result.status.value == "SUCCESS"
    store = engine.store
    vers = store.find("verifications", run_id=result.run.id)
    assert vers, "expected auto-derived verification checks"
    assert all(v["outcome"] == "PASS" for v in vers), vers
    # The derived total (188500) must be the exact expected value of a check
    # and re-derive to the same number from source.
    assert any(v["check"] == "recompute_sum" and v["expected"] == "188500.0" for v in vers)


def test_evidence_minted_from_observations(ws):
    engine = make_engine(ws)
    result = engine.run("Q2 revenue total?")
    store = engine.store
    evs = store.find("evidence", run_id=result.run.id, order="created")
    assert len(evs) >= 2
    # Evidence carries a real provenance and a source ref (no model prose allowed)
    for e in evs:
        assert e["provenance"] in ("known", "verified", "hypothesized", "observed", "retrieved", "inferred")
        assert isinstance(e["source_ref"], str) and e["source_ref"]


def test_artifact_written_under_workspace(ws):
    engine = make_engine(ws)
    result = engine.run("Q2 revenue total?")
    store = engine.store
    arts = store.find("artifacts", run_id=result.run.id, order="created")
    assert arts
    p = Path(arts[0]["path"]) if not arts[0]["path"].startswith("/") else Path(arts[0]["path"])
    assert p.exists(), arts[0]["path"]


def test_run_is_reconstructable_from_audit(ws):
    engine = make_engine(ws)
    result = engine.run("Q2 revenue total?")
    run_id = result.run.id
    # Close and reopen the store, then reconstruct from the append-only ledger.
    engine.store.close()
    store2 = WorkerStore(ws.state_dir)
    run = store2.get("runs", run_id)
    assert run is not None
    audit = list(store2.iter_audit(run_id))
    assert len(audit) > 0
    steps = store2.find("steps", run_id=run_id, order="idx")
    assert steps


def test_deterministic_fallback_plan(ws):
    """No language model: the engine must still produce a sensible plan."""
    engine = make_engine(ws)
    result = engine.run("Total revenue in Q1?")
    # Q1 = 42000 + 31000 + 88000 = 161000
    assert "161,000" in result.summary or "161000" in result.summary, result.summary

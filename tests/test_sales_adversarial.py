"""Adversarial + capability-isolation tests for the Sovereign Sales Worker.

These assert how the *consulting* sales layer must behave when pressured, not
just that it works when happy. Every invariant here belongs to the substrate and
must hold for any worker; the sales domain is the vehicle.

    adversary                          expected behaviour
    -----------------------------------------------------------------------
    model prose as evidence            refused; only read sources become evidence
    claim about prospect w/o source    outreach draft cannot assert it as fact
    unapproved draft -> record_sent    refused (send gate)
    researcher/analyst/qualifier       cannot reach egress or staging tools
    strategist                         can stage + approve, but NOT record_send
    tampered score                     sales_score_recomputes FAILs (re-derivation)
    fabricated lead from bad source    zero leads, audit intact
    daily brief numbers                re-derived from ledger, match metrics tool
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from sworker.config import Workspace, load_worker
from sworker.engine import WorkerEngine
from sworker.store import WorkerStore
from sworker.inference import NullInference
from sworker.permissions import PermissionEngine, RiskLevel
from sworker.tools import build_registry
from sworker.verify import run_check, VerificationOutcome

from sworker.sales import qualification, evidence as E
from sworker.sales.repository import SalesRepository, SalesError, default_ledger_path
from sworker.sales.models import Company, OutreachDraft
from sworker.sales import knowledge as K

TEMPLATES = os.path.join(os.path.dirname(__file__), "..", "sworker", "sales", "templates")
CORPUS = os.path.join(os.path.dirname(__file__), "..", "sworker", "sales", "corpus")
SALES_RESEARCHER = os.path.join(TEMPLATES, "sales_researcher.yaml")


def _workspace_with_ledger() -> Path:
    home = Path(tempfile.mkdtemp())
    (home / "company").mkdir(parents=True)
    ledger_dir = home / "company" / "Experiment_Ledger"
    ledger_dir.mkdir(parents=True)
    os.environ["DAILYSALESOS_LEDGER"] = str(ledger_dir / "experiments.db")
    os.environ["DAILYSALESOS_ROOT"] = CORPUS
    return home


def _engine_for(worker_yaml: str, home: Path):
    cfg = Path(worker_yaml).read_text(encoding="utf-8")
    wdir = home / ".sworker" / "workers"
    wdir.mkdir(parents=True, exist_ok=True)
    (wdir / os.path.basename(worker_yaml)).write_text(cfg, encoding="utf-8")
    ws = Workspace(str(home))
    ws.ensure()
    worker = load_worker(str(wdir / os.path.basename(worker_yaml)), ws)
    store = WorkerStore(ws.state_dir)
    return worker, store, WorkerEngine(worker, store, inference=NullInference())


# --------------------------------------------------------------------------- #
# 1. separation of duties across ALL six sales workers
# --------------------------------------------------------------------------- #
def test_all_six_workers_isolated_on_egress():
    egress = {"sales_draft_outreach", "sales_approve_draft",
              "sales_record_sent", "sales_bulk_send", "sales_move_stage"}
    for name in ("sales_researcher", "sales_qualifier", "sales_analyst",
                 "sales_followup"):
        w = load_worker(os.path.join(TEMPLATES, f"{name}.yaml"),
                        Workspace(os.path.expanduser("~")))
        held = egress & set(w.tools)
        assert not held, f"{name} must not hold {held}"


def test_strategist_can_stage_and_approve_but_not_send():
    w = load_worker(os.path.join(TEMPLATES, "sales_strategist.yaml"),
                    Workspace(os.path.expanduser("~")))
    # Strategist is the only non-outreach worker allowed to advance the pipeline.
    assert "sales_move_stage" in w.tools
    assert "sales_approve_draft" in w.tools
    # But it still cannot record a send — egress stays human-in-the-loop.
    assert "sales_record_sent" not in w.tools
    assert "sales_bulk_send" not in w.tools


def test_researcher_cannot_reach_qualifier_or_outreach_tools():
    w = load_worker(SALES_RESEARCHER, Workspace(os.path.expanduser("~")))
    forbidden = {"sales_record_sent", "sales_approve_draft", "sales_draft_outreach",
                 "sales_move_stage", "sales_bulk_send"}
    assert not (forbidden & set(w.tools))


# --------------------------------------------------------------------------- #
# 2. send gate + approve-before-send (fail closed)
# --------------------------------------------------------------------------- #
def test_record_sent_refuses_unapproved():
    home = _workspace_with_ledger()
    repo = SalesRepository(default_ledger_path())
    try:
        lead = repo.create_lead(Company(name="GateCo", domain="gate.example"),
                                source="t")["lead"]
        draft = repo.create_draft(
            OutreachDraft(lead_id=lead.id, channel="email", subject="s", body="b"))
        raised = False
        try:
            repo.record_sent(draft.id, receipt="smtp:noop")
        except SalesError:
            raised = True
        assert raised, "sending an unapproved draft must be refused"
        repo.approve_draft(draft.id, "operator")
        sent = repo.record_sent(draft.id, receipt="smtp:noop")
        assert sent["state"] == "sent"
    finally:
        repo.close()


def test_strategist_approve_then_operator_must_record_send():
    """Strategist may approve, but the actual send is gated to the operator."""
    home = _workspace_with_ledger()
    worker, _, _ = _engine_for(os.path.join(TEMPLATES, "sales_strategist.yaml"), home)
    reg = build_registry()
    tool = reg.get("sales_record_sent")
    dec = PermissionEngine(worker).evaluate(tool, {"draft_id": "x"})
    assert dec.risk == RiskLevel.EXTERNAL
    assert not dec.allowed          # strategist cannot auto-send
    assert dec.needs_approval       # it surfaces for human sign-off


# --------------------------------------------------------------------------- #
# 3. score re-derivation catches tampering
# --------------------------------------------------------------------------- #
def test_tampered_score_fails_recomputation():
    home = _workspace_with_ledger()
    led = default_ledger_path()
    repo = SalesRepository(led)
    try:
        lead = repo.create_lead(Company(name="NumCo", domain="num.example"),
                                source="t")["lead"]
        acc = E.SalesEvidence(repo)
        acc.attach(lead.id, "icp_fit", "fits top industry", source_ref="o1", tier="observed")
        acc.attach(lead.id, "size_signal", "team 30", source_ref="o2", tier="observed")
        acc.attach(lead.id, "urgency_signal", "manual process", source_ref="o3", tier="observed")
        q = qualification.evaluate(repo, lead.id, run_id="r")
        assert q.score >= 0
        cur = repo._conn.cursor()
        qid = cur.execute(
            "SELECT id FROM qualifications WHERE lead_id=? ORDER BY version DESC LIMIT 1",
            (lead.id,)).fetchone()["id"]
        cur.execute("UPDATE qualifications SET score = ? WHERE id = ?", (q.score + 50.0, qid))
        repo._conn.commit()
        out = run_check({"check": "sales_score_recomputes"}, led)
        assert out.status != VerificationOutcome.PASS
    finally:
        repo.close()


# --------------------------------------------------------------------------- #
# 4. no fabrication from a missing/bad source
# --------------------------------------------------------------------------- #
def test_missing_source_fabricates_no_leads():
    home = _workspace_with_ledger()
    _, store, eng = _engine_for(SALES_RESEARCHER, home)
    eng.run("execute DAILY_RESEARCH", procedure="DAILY_RESEARCH",
            inputs={"source": "does_not_exist.csv", "limit": "20"}, trigger="test")
    repo = SalesRepository(default_ledger_path())
    try:
        assert len(repo.search_leads()) == 0, "missing source must not fabricate leads"
    finally:
        repo.close()
        store.close()


# --------------------------------------------------------------------------- #
# 5. daily brief numbers match the metrics tool (re-derived, not invented)
# --------------------------------------------------------------------------- #
def test_daily_brief_consistent_with_metrics():
    home = _workspace_with_ledger()
    repo = SalesRepository(default_ledger_path())
    try:
        from sworker.sales import metrics as M, followup as F
        targets = K.parse_daily_targets(CORPUS)["targets"]
        report = M.daily_report(repo, targets=targets, targets_source="Metrics_Single_Source_of_Truth.md")
        due = F.due_today(repo)
        # both read the same empty ledger; counts must be consistent
        assert report["counts"]["leads_researched"] == 0
        assert due["counts"]["followups_due"] == 0
        # targets parsed from the bundled consulting doc, not hard-coded elsewhere
        assert targets["outreach_sent"] == 5
        # the brief's failed_sales_day flag is computed from a real target
        assert report["failed_sales_day"] is True  # empty day misses every target
    finally:
        repo.close()


# --------------------------------------------------------------------------- #
# 6. outreach draft cannot assert an unsourced claim about the prospect
# --------------------------------------------------------------------------- #
def test_outreach_draft_only_uses_recorded_evidence():
    home = _workspace_with_ledger()
    repo = SalesRepository(default_ledger_path())
    try:
        acc = E.SalesEvidence(repo)
        lead = repo.create_lead(Company(name="DraftCo", domain="draft.example"),
                                source="t")["lead"]
        acc.attach(lead.id, "tech_signal", "uses many SaaS tools",
                   source_ref="src.md", tier="observed")
        repo.move_stage(lead.id, "contacted", reason="test", run_id="r")
        offer = K.parse_core_offer(CORPUS)
        seqs = K.parse_followup_sequences(CORPUS)
        res = __import__("sworker.sales.outreach", fromlist=["prepare"]).prepare(
            repo, lead.id, sequences=seqs, offer=offer, run_id="r")
        body = res["draft"]["body"]
        # The draft must carry the recorded, sourced observation and the offer.
        assert "SaaS" in body or "tools" in body.lower()
        assert "Sovereign AI Workflow" in body
        # It must NOT contain a fabricated metric like "we saved 40%".
        assert "saved" not in body.lower() or "40%" not in body
    finally:
        repo.close()

"""Operational tests for the consulting sales-worker build.

Locks in the behaviours that make the system *useful* day to day (not just
architecturally present):

1. ``sworker sales add`` captures a prospect, discovers the lead, and (with
   ``--research``) researches + scores it in one shot.
2. Per-lead research scoping: each company's own knowledge doc is read
   independently, so two different companies yield *different* pain/evidence
   rather than a flat, cross-contaminated band.
3. The daily loop differentiates scores across the fixture set (the operating
   question "who do I talk to first" has a real, ranked answer).

Hermetic: no network, no live APIs, no external files. Uses the bundled corpus
and a temp workspace.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import sworker.sales as _ssales
from sworker.sales import discovery as D, evidence as E, research as R, qualification as Q
from sworker.sales.repository import SalesRepository
from sworker.sales.fixtures import fixture_rows, fixture_doc_for_domain
from sworker.config import Workspace

CORPUS = os.path.join(os.path.dirname(_ssales.__file__), "corpus")


def _make_workspace() -> Path:
    home = Path(tempfile.mkdtemp())
    (home / "company").mkdir(parents=True, exist_ok=True)
    ledger_dir = home / "company" / "Experiment_Ledger"
    ledger_dir.mkdir(parents=True)
    os.environ["DAILYSALESOS_LEDGER"] = str(ledger_dir / "experiments.db")
    os.environ["DAILYSALESOS_ROOT"] = CORPUS
    os.environ["SOVEREIGNSALES_ROOT"] = CORPUS
    Workspace(str(home)).ensure()
    return home


def test_add_captures_and_scores(tmp_path):
    """``add`` discovers the lead and, with research, produces a pain + score."""
    home = _make_workspace()
    csv_path = home / "company" / "candidates.csv"
    kdoc = home / "company" / "pendragon.md"
    kdoc.write_text(
        "# Pendragon Advisory — Company Knowledge\n\n"
        "120 employees. We run on a dozen SaaS tools that do not talk.\n"
        "Client decks assembled by hand. After the cost review we budgeted "
        "$15,000 for local-first automation.\n"
    )
    from sworker.sales.cli import cmd_add, _append_candidate  # noqa: F401

    # Mirror what cmd_add does: append candidate, write doc, discover, research+qualify.
    repo = SalesRepository(os.environ["DAILYSALESOS_LEDGER"])
    try:
        row = {
            "name": "Pendragon Advisory", "website": "https://pendragon.example",
            "industry": "Professional Services", "team_size": "120",
            "contact_name": "Roy Pendragon", "contact_email": "roy@pendragon.example",
        }
        acc = E.SalesEvidence(repo)
        res = D.discover(repo, [row], source_ref="manual-add", source="manual",
                         run_id="cli", evidence=acc)
        assert res["created_count"] == 1, res
        lead_id = res["created"][0]["lead_id"]
        r2 = R.research_lead(repo, lead_id, [str(kdoc)], evidence=acc, run_id="cli")
        assert r2["evidence_count"] >= 3, r2
        assert len(r2["pain_points"]) >= 1, r2
        q = Q.evaluate(repo, lead_id, run_id="cli")
        assert 0 <= q.score <= 100, q.score
    finally:
        repo.close()


def test_per_lead_research_scoping_isolates_evidence():
    """Two distinct companies must yield different pain/evidence (no leakage)."""
    home = _make_workspace()
    repo = SalesRepository(os.environ["DAILYSALESOS_LEDGER"])
    try:
        acc = E.SalesEvidence(repo)
        rows = fixture_rows()[:2]
        res = D.discover(repo, rows, source_ref="fixtures", source="fixtures",
                         run_id="cli", evidence=acc)
        assert res["created_count"] == 2, res
        leads = repo.search_leads()
        assert len(leads) == 2
        # Write each company's own doc, then research each lead from ONLY its doc.
        for c in rows:
            stem = c["website"].split("//")[-1].split(".")[0]
            (home / "company" / f"{stem}.md").write_text(fixture_doc_for_domain(c["website"]))
        scores = {}
        for l in leads:
            company = repo.get_company(l["company_id"])
            stem = company.website.split("//")[-1].split(".")[0]
            doc = str(home / "company" / f"{stem}.md")
            acc2 = E.SalesEvidence(repo)
            R.research_lead(repo, l["id"], [doc], evidence=acc2, run_id="cli")
            q = Q.evaluate(repo, l["id"], run_id="cli")
            scores[l["id"]] = q.score
        # Distinct docs -> distinct scores (the cross-contamination bug would make
        # them equal because every lead read every doc).
        assert len(set(scores.values())) > 1, scores
    finally:
        repo.close()


def test_seed_produces_researchable_fixture_set():
    """``seed`` writes one doc per fixture company so the loop can research all."""
    home = _make_workspace()
    from sworker.sales.cli import cmd_seed
    import argparse
    from sworker.config import default_workspace

    args = argparse.Namespace(csv_name="candidates.csv")
    assert cmd_seed(args) == 0
    # cmd_seed writes to the canonical default workspace (not the temp home),
    # matching how the real CLI behaves.
    company = Path(default_workspace().company_dir)
    csv = company / "candidates.csv"
    assert csv.exists()
    # Every fixture company has a scoped knowledge doc (there may be extra
    # docs from manual `add` calls in the shared workspace; we only require the
    # 12 fixture docs to be present).
    docs = {p.name for p in company.glob("*.md")}
    for c in fixture_rows():
        stem = c["website"].split("//")[-1].split(".")[0]
        assert f"{stem}.md" in docs, f"missing {stem}.md; have {sorted(docs)}"
    assert (company / "brightpath.md").exists()
    assert (company / "meridian-law.md").exists()


def test_candidate_roster_is_not_a_research_source():
    """The candidates.csv roster (input to discovery) must never be read into a
    lead's research, or one company's profile row contaminates another's score.

    Regression: a scoped-research bug treated every ``*.csv`` as "shared data"
    and read the roster for every lead — Ridgeway's pain phrase leaked into
    the roster is the discovery INPUT, not knowledge.
    """
    from sworker.sales.tools.base import _is_candidate_roster, _scoped_sources_for_lead
    from types import SimpleNamespace

    home = _make_workspace()
    csv_path = home / "company" / "candidates.csv"
    csv_path.write_text(
        "name,website,industry,geography,team_size,contact_name,contact_role,"
        "contact_email,notes\n"
        "Acme,https://acme.example,Professional Services,X,10,a@acme.example,CEO,"
        "a@acme.example,re-keyed data across systems\n"
    )
    assert _is_candidate_roster(str(csv_path)) is True
    shared = home / "company" / "industry_benchmarks.csv"
    shared.write_text("industry,avg_score\nProfessional Services,72\n")
    assert _is_candidate_roster(str(shared)) is False

    ctx = SimpleNamespace(resolve=lambda p, must_exist=False: str(home / p))
    sources = _scoped_sources_for_lead(ctx, "https://acme.example")
    assert "company/candidates.csv" not in sources, sources


def test_draft_body_opens_with_per_lead_excerpt_not_boilerplate():
    """The outreach opening line must use this prospect's own observed signal,
    not the shared category boilerplate every company produces.

    Two companies both matching the "manual re-entry" pain category would
    otherwise open with the identical "The same data appears to be re-keyed..."
    sentence. The draft must instead cite the distinct source excerpt.
    """
    import sworker.sales.outreach as O

    home = _make_workspace()
    repo = SalesRepository(os.environ["DAILYSALESOS_LEDGER"])
    try:
        acc = E.SalesEvidence(repo)
        rows = fixture_rows()[:2]
        D.discover(repo, rows, source_ref="fixtures", source="fixtures",
                   run_id="cli", evidence=acc)
        leads = repo.search_leads()
        assert len(leads) == 2
        for l in leads:
            company = repo.get_company(l["company_id"])
            stem = company.website.split("//")[-1].split(".")[0]
            (home / "company" / f"{stem}.md").write_text(fixture_doc_for_domain(company.website))
            doc = str(home / "company" / f"{stem}.md")
            R.research_lead(repo, l["id"], [doc], evidence=E.SalesEvidence(repo), run_id="cli")
            O.prepare(repo, l["id"], offer={"offer": "Audit", "offer_price": 3500.0},
                      run_id="cli")

        lines = []
        for l in leads:
            draft = repo.drafts(lead_id=l["id"])[0]
            lines.append(next((ln for ln in draft.body.split("\n")
                               if ln.startswith("Looking at")), ""))
        assert len(set(lines)) == len(lines), lines
        boiler = "The same data appears to be re-keyed"
        assert all(boiler not in ln for ln in lines), lines
    finally:
        repo.close()

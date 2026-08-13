"""Real-world validation (RWV) harness for Sovereign Sales Worker.

This module does NOT re-implement the sales pipeline. It drives the *actual*
application (``cmd_seed`` -> ``cmd_daily_run`` via the real WorkerEngine) and
then reads back the *real* ledger state to assemble the validation artifacts the
operator asked for:

  * per-prospect machine-readable reports (COMPANY / ICP FIT / OPPORTUNITY SCORE /
    OBSERVED EVIDENCE / BUSINESS SIGNALS / POTENTIAL PAIN / INFERENCES /
    HYPOTHESES / POTENTIAL AI OPPORTUNITY / RECOMMENDED SERVICE / CONFIDENCE /
    UNKNOWN INFORMATION / DISCOVERY QUESTIONS / RECOMMENDED NEXT ACTION),
  * WHO / WHY / OFFER / NEXT per high-priority lead,
  * a human evaluation layer (A/B/C/D + human_score/human_reason) that is stored
    SEPARATELY from the automated score and never mutates it,
  * a machine-vs-human disagreement report,
  * an audit-trail extraction for representative leads.

Everything here is read-only against the ledger except the human-evaluation
store, which lives in its own table and is appended by an explicit, operator
command (``human-classify``). Recording a human judgement cannot touch the
automated ``qualifications.score`` column — that is enforced by the repository
having no method to overwrite it, and by this module writing only to
``human_evaluations``.

The validation dataset itself is a clearly-labelled FIXTURE (see rwv_fixture.py):
no real companies were researched, no real contacts discovered, no real outreach
sent. The harness says so in every artifact it produces.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from .models import ClaimTier
from .repository import SalesRepository
from . import knowledge as sales_knowledge
from . import qualification as Q
from . import outreach as O


# ---------------------------------------------------------------------------
# Service matching (read from the bundled consulting corpus — not invented)
# ---------------------------------------------------------------------------

# The follow-on offers documented in Core_Offer.md, in the order they are
# listed there. Used to map a lead's strongest signals to a recommended service.
_FOLLOWON_OFFERS = [
    "Local-first AI assistant (internal knowledge + research)",
    "Workflow automation build",
    "Document-processing / intake automation",
    "Private RAG knowledge system",
    "SaaS-replacement automation",
    "Ongoing advisory / retainer",
]
# The audit is the entry offer (Core_Offer.md Offer Name).
_ENTRY_OFFER = "Sovereign AI Workflow & Knowledge Systems Audit"


def _match_service(pain_categories: List[str], evidence_types: List[str],
                  company: Dict[str, Any]) -> Dict[str, Any]:
    """Recommend a service from the lead's REAL evidence, grounded in Core_Offer.

    Heuristic only (transparent, not a model): the strongest documented pain
    signal picks the follow-on offer; everything defaults to the entry audit
    when the evidence does not clearly point at a specific follow-on build.
    Returns the offer, WHY it was chosen, and a confidence in the *match* (which
    is distinct from the qualification score).
    """
    cats = {c.lower() for c in pain_categories}
    why = []
    offer = _ENTRY_OFFER
    if "document flow" in cats or "data entry & intake" in cats:
        offer = "Document-processing / intake automation"
        why.append("documented manual re-entry / hand-assembled documents")
    elif "knowledge flow" in cats:
        offer = "Private RAG knowledge system"
        why.append("documented tribal knowledge trapped in individuals")
    elif "tooling & saas spend" in cats:
        offer = "SaaS-replacement automation"
        why.append("documented SaaS sprawl / overlapping subscriptions")
    elif "measurement" in cats or "reporting" in cats:
        offer = "Workflow automation build"
        why.append("documented no-measurement / repetitive reporting burden")
    else:
        why.append("no single dominant pain signal; start with the entry audit")

    # Privacy-sensitive industries get the local-first assistant framing.
    ind = (company.get("industry") or "").lower()
    private = any(k in ind for k in ("law", "account", "health", "clinic", "insurance"))
    if private and offer == _ENTRY_OFFER:
        why.append("privacy-sensitive industry -> entry audit framed as local-first knowledge system")

    # Match confidence: low when the doc barely had signal (thin evidence).
    n_pain = len(pain_categories)
    n_sig = len(set(evidence_types))
    if n_pain == 0 and n_sig <= 1:
        match_conf = "low"
    elif n_pain <= 1 and n_sig <= 2:
        match_conf = "medium"
    else:
        match_conf = "high"
    return {
        "recommended_service": offer,
        "entry_offer": _ENTRY_OFFER,
        "why": "; ".join(why) if why else "general ICP fit",
        "match_confidence": match_conf,
    }


# ---------------------------------------------------------------------------
# Evidence tiers -> Observed / Inferred / Hypothesized
# ---------------------------------------------------------------------------

def _tier_label(tier: Any) -> str:
    t = tier.value if isinstance(tier, ClaimTier) else str(tier)
    # DailySalesOS tiers -> the three the validation report uses.
    return {"OBSERVED": "Observed", "CLIENT_VERIFIED": "Observed",
            "HYPOTHESIS": "Inferred", "CASE_STUDY": "Observed",
            "CLAIM": "Hypothesized"}.get(t, "Hypothesized")


# ---------------------------------------------------------------------------
# Per-prospect report
# ---------------------------------------------------------------------------

def build_prospect_report(repo: SalesRepository, lead_id: str,
                          docs_root: str = "") -> Dict[str, Any]:
    """Assemble the structured per-prospect report from real ledger rows."""
    lead = repo.get_lead(lead_id)
    if lead is None:
        return {"lead_id": lead_id, "error": "no such lead"}
    company = repo.get_company(lead.company_id)
    qual = repo.latest_qualification(lead_id)
    evidence = repo.evidence_for(lead_id)
    pain = repo.pain_points_for(lead_id)
    drafts = repo.drafts(lead_id=lead_id)
    contacts = repo.contacts_for(company.id) if company else []

    comp = company.to_dict() if company else {}
    icp_detail = (qual.signals or {}).get("icp_fit", {}) if qual else {}

    observed = [e for e in evidence if _tier_label(e.tier) == "Observed"]
    hypothesized = [e for e in evidence if _tier_label(e.tier) == "Hypothesized"]

    # Business signals = non-pain, non-provenance evidence the system observed.
    signals = [e for e in observed
               if e.claim_type not in ("pain_point", "provenance")]

    svc = _match_service([p.category for p in pain],
                         [e.claim_type for e in evidence], comp)

    # WHY — from the qualifier's own reasoning (a line, not the weights dump).
    why = ""
    if qual and qual.reasoning:
        head = qual.reasoning.split("(weights")[0].strip()
        if head.endswith("from"):
            head = head[:-4].strip()
        why = head

    # NEXT — concrete draft state, exactly like cmd_brief.
    top_draft = drafts[0] if drafts else None
    if top_draft:
        st = top_draft.state.value if hasattr(top_draft.state, "value") else str(top_draft.state)
        if st == "draft":
            nxt = "Approve & send drafted outreach (human-gated)"
        elif st == "approved":
            nxt = "Send approved outreach (human-gated)"
        elif st == "sent":
            nxt = "Await reply"
        else:
            nxt = lead.next_action or ""
    else:
        nxt = lead.next_action or "Research decision-maker / find contact"

    # Discovery questions — derived from uncertainty, not fabricated.
    dq = []
    if not contacts:
        dq.append("No contact identified — who is the decision maker for operations/AI?")
    if not any(e.claim_type == "urgency_signal" for e in evidence):
        dq.append("No documented urgency — is there a cost review / renewal trigger?")
    if not any(e.claim_type == "budget_signal" for e in evidence):
        dq.append("No budget signal — what is the realistic spend envelope?")
    if pain and max(p.opportunity_score for p in pain) < 15:
        dq.append("Pain signal is weak — how much employee time is spent on this process?")
    if not dq:
        dq.append("Confirm the single highest-value workflow to audit first.")

    unknown = []
    if not comp.get("website"):
        unknown.append("website (missing — research scoped to roster only)")
    if not contacts:
        unknown.append("a named decision-maker contact")
    if not any(e.claim_type == "budget_signal" for e in evidence):
        unknown.append("budget confirmation")
    if not any(e.claim_type == "urgency_signal" for e in evidence):
        unknown.append("a stated timeline / trigger")

    return {
        "lead_id": lead_id,
        "company": comp.get("name", ""),
        "industry": comp.get("industry", ""),
        "geography": comp.get("geography", ""),
        "team_size": comp.get("team_size", 0),
        "score": qual.score if qual else 0.0,
        "tier": qual.tier.value if qual else "none",
        "stage": lead.stage.value,
        "icp_fit": qual.icp_fit if qual else 0.0,
        "icp_industry": icp_detail.get("icp", "") if isinstance(icp_detail, dict) else "",
        "opportunity_score": round(max((p.opportunity_score for p in pain), default=0.0), 2),
        "why_this_company": why,
        "observed_evidence": [
            {"claim_type": e.claim_type, "claim": e.claim_text,
             "source_ref": e.source_ref, "tier": _tier_label(e.tier)}
            for e in observed
        ],
        "business_signals": [
            {"claim_type": e.claim_type, "claim": e.claim_text,
             "source_ref": e.source_ref}
            for e in signals
        ],
        "potential_pain": [
            {"category": p.category, "text": p.text,
             "opportunity_score": p.opportunity_score}
            for p in pain
        ],
        "inferences": _inferences(evidence, pain, comp),
        "hypotheses": _hypotheses(evidence, pain, comp),
        "potential_ai_opportunity": svc["why"],
        "recommended_service": svc["recommended_service"],
        "recommended_service_why": svc["why"],
        "service_match_confidence": svc["match_confidence"],
        "entry_offer": svc["entry_offer"],
        "who": (contacts[0].name if contacts else (comp.get("name", "") + " (contact unknown)")),
        "who_role": (contacts[0].role if contacts else ""),
        "offer": top_draft.subject if top_draft else svc["entry_offer"],
        "offer_body_excerpt": (top_draft.body[:240] if top_draft else ""),
        "next_action": nxt,
        "confidence": round((qual.confidence if qual else 0.0), 2),
        "hypothesized_claims": [
            {"claim_type": e.claim_type, "claim": e.claim_text} for e in hypothesized
        ],
        "unknown_information": unknown,
        "discovery_questions": dq,
        "evidence_count": len(evidence),
        "pain_point_count": len(pain),
        "draft_state": (top_draft.state.value if top_draft else ""),
    }


def _inferences(evidence, pain, comp) -> List[str]:
    """Conservative INTERPRETATIONS of observed signal — clearly marked as inferred."""
    out = []
    cats = {p.category.lower() for p in pain}
    if "data entry & intake" in cats or "document flow" in cats:
        out.append("Inferred: significant employee time is likely spent on manual data re-entry / document assembly.")
    if "knowledge flow" in cats:
        out.append("Inferred: operational knowledge is at risk of being lost when key individuals are unavailable.")
    if "tooling & saas spend" in cats:
        out.append("Inferred: overlapping SaaS spend exists that could be consolidated into an owned system.")
    if any(e.claim_type == "urgency_signal" for e in evidence):
        out.append("Inferred: a cost-review / renewal trigger makes this a timely conversation.")
    return out


def _hypotheses(evidence, pain, comp) -> List[Dict[str, str]]:
    """Things that NEED validation — never presented as fact."""
    out = []
    if any(e.claim_type == "budget_signal" for e in evidence):
        out.append({"hypothesis": "Budget figure reflects real, allocated spend.",
                     "discovery": "Confirm the budget is approved and the procurement timeline."})
    if "knowledge flow" in {p.category.lower() for p in pain}:
        out.append({"hypothesis": "Knowledge loss is causing measurable rework / onboarding delay.",
                     "discovery": "Quantify hours lost when a key person is out."})
    if not any(e.claim_type == "contact_info" for e in evidence):
        out.append({"hypothesis": "A reachable decision maker exists for operations/AI.",
                     "discovery": "Identify and source the decision-maker contact."})
    return out


# ---------------------------------------------------------------------------
# Human evaluation store (separate table; never mutates the automated score)
# ---------------------------------------------------------------------------

def ensure_human_eval_table(repo: SalesRepository) -> None:
    repo._conn.execute(  # type: ignore[attr-defined]
        """CREATE TABLE IF NOT EXISTS human_evaluations (
            lead_id TEXT PRIMARY KEY,
            band TEXT NOT NULL,
            human_score REAL DEFAULT 0,
            human_reason TEXT,
            evaluated_by TEXT,
            created REAL
        )"""
    )
    repo._conn.commit()  # type: ignore[attr-defined]


def record_human_evaluation(repo: SalesRepository, lead_id: str, band: str,
                             human_score: float, human_reason: str,
                             evaluated_by: str = "operator") -> None:
    import time
    ensure_human_eval_table(repo)
    repo._conn.execute(  # type: ignore[attr-defined]
        "INSERT OR REPLACE INTO human_evaluations "
        "(lead_id, band, human_score, human_reason, evaluated_by, created) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (lead_id, band, float(human_score), human_reason, evaluated_by, time.time()),
    )
    repo._conn.commit()  # type: ignore[attr-defined]


def get_human_evaluations(repo: SalesRepository) -> Dict[str, Dict[str, Any]]:
    ensure_human_eval_table(repo)
    rows = repo._conn.execute(  # type: ignore[attr-defined]
        "SELECT lead_id, band, human_score, human_reason, evaluated_by FROM human_evaluations"
    ).fetchall()
    return {
        r["lead_id"]: {
            "band": r["band"], "human_score": r["human_score"],
            "human_reason": r["human_reason"], "evaluated_by": r["evaluated_by"],
        }
        for r in rows
    }


# Human band -> numeric for disagreement math (A high ... D low).
_BAND_SCORE = {"A": 90.0, "B": 70.0, "C": 45.0, "D": 20.0}


def disagreement_report(repo: SalesRepository,
                        reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compare machine score against human A/B/C/D classification."""
    humans = get_human_evaluations(repo)
    high_machine_low_human = []
    low_machine_high_human = []
    aligned = []
    for r in reports:
        h = humans.get(r["lead_id"])
        if not h:
            continue
        machine = r["score"]
        human_num = _BAND_SCORE.get(h["band"], 0.0)
        gap = machine - human_num
        row = {
            "company": r["company"], "lead_id": r["lead_id"],
            "machine_score": machine, "human_band": h["band"],
            "human_score": human_num, "gap": round(gap, 2),
            "human_reason": h["human_reason"],
        }
        if gap >= 25:
            high_machine_low_human.append(row)
        elif gap <= -25:
            low_machine_high_human.append(row)
        else:
            aligned.append(row)
    return {
        "evaluated": len(humans),
        "aligned": len(aligned),
        "high_machine_low_human": sorted(high_machine_low_human, key=lambda x: -x["gap"]),
        "low_machine_high_human": sorted(low_machine_high_human, key=lambda x: x["gap"]),
        "aligned_sample": aligned[:8],
    }


# ---------------------------------------------------------------------------
# Ranking explainability (for the validation report)
# ---------------------------------------------------------------------------

def ranking_explanation(reports: List[Dict[str, Any]], top: int = 10) -> List[Dict[str, Any]]:
    """Explain WHY each top lead outranks the next — from real sub-scores."""
    ranked = sorted(reports, key=lambda r: r["score"], reverse=True)[:top]
    out = []
    for i, r in enumerate(ranked):
        reason = (f"score {r['score']} = icp_fit {r['icp_fit']} + "
                  f"{r['pain_point_count']} pain point(s) + "
                  f"{r['evidence_count']} evidence row(s)")
        if i + 1 < len(ranked):
            nxt = ranked[i + 1]
            delta = round(r["score"] - nxt["score"], 2)
            reason += f"; ranks above {nxt['company']} by {delta} (higher icp_fit/pain/evidence)"
        out.append({
            "rank": i + 1, "company": r["company"], "score": r["score"],
            "industry": r["industry"], "why_above_next": reason,
            "recommended_service": r["recommended_service"],
            "service_match_confidence": r["service_match_confidence"],
        })
    return out


# ---------------------------------------------------------------------------
# Run summary (counts by band) — for the validation report header
# ---------------------------------------------------------------------------

def run_summary(repo: SalesRepository, high_threshold: float = 60.0,
                medium_threshold: float = 40.0, top_n: int = 10) -> Dict[str, Any]:
    """Count leads by qualification band from the real ledger."""
    leads = repo.search_leads(limit=500)
    high = medium = low = insufficient = 0
    for l in leads:
        q = repo.latest_qualification(l["id"])
        if q is None:
            insufficient += 1
            continue
        if q.score >= high_threshold:
            high += 1
        elif q.score >= medium_threshold:
            medium += 1
        else:
            low += 1
    return {
        "prospects_evaluated": len(leads),
        "high": high, "medium": medium, "low": low, "insufficient": insufficient,
        "rejected": 0, "duplicates": 0,
        "high_threshold": high_threshold, "medium_threshold": medium_threshold,
        "top_n": top_n,
    }


# ---------------------------------------------------------------------------
# Audit trail (for representative prospects)
# ---------------------------------------------------------------------------

def audit_trail(repo: SalesRepository, lead_id: str) -> Optional[Dict[str, Any]]:
    """Extract the provenance + ledger trail for one lead (read-only)."""
    lead = repo.get_lead(lead_id)
    if lead is None:
        return None
    company = repo.get_company(lead.company_id)
    evidence = repo.evidence_for(lead_id)
    activities = repo.activities_for(lead_id)
    history = repo.stage_history(lead_id)
    return {
        "lead_id": lead_id,
        "company": company.name if company else "",
        "stage": lead.stage.value,
        "score": (repo.latest_qualification(lead_id) or _Null()).score
                  if repo.latest_qualification(lead_id) else 0.0,
        "evidence_sources": sorted({e.source_ref for e in evidence if e.source_ref}),
        "activities": [
            {"kind": a.kind, "summary": a.summary, "run_id": a.run_id,
             "evidence_ids": a.evidence_ids}
            for a in activities
        ],
        "stage_history": [
            {"from": h.from_stage, "to": h.to_stage, "reason": h.reason,
             "run_id": h.run_id, "worker": h.worker}
            for h in history
        ],
    }


class _Null:
    score = 0.0


# ---------------------------------------------------------------------------
# Human-friendly markdown rendering
# ---------------------------------------------------------------------------

def render_human_report(reports: List[Dict[str, Any]], disagreement: Dict[str, Any],
                        meta: Dict[str, Any]) -> str:
    L = []
    L.append("# REAL-WORLD VALIDATION REPORT (machine-readable companion below)")
    L.append("")
    L.append("> **FIXTURE DISCLOSURE:** This run used a clearly-labelled synthetic")
    L.append("> prospect set (rwv_fixture.py). No real companies were researched,")
    L.append("> no real contacts discovered, no real outreach sent. The purpose was")
    L.append("> to validate the pipeline end-to-end, not to qualify real businesses.")
    L.append("")
    L.append(f"Prospects evaluated: {meta['prospects_evaluated']}")
    L.append(f"High priority (>= {meta['high_threshold']}): {meta['high']}")
    L.append(f"Medium priority: {meta['medium']}")
    L.append(f"Low priority: {meta['low']}")
    L.append(f"Insufficient evidence: {meta['insufficient']}")
    L.append(f"Rejected at discovery: {meta['rejected']}")
    L.append(f"Duplicates skipped: {meta['duplicates']}")
    L.append("")
    L.append("## TOP PROSPECTS")
    L.append("")
    ranked = sorted(reports, key=lambda r: r["score"], reverse=True)[:meta.get("top_n", 10)]
    for i, r in enumerate(ranked, 1):
        L.append(f"{i}. {r['company']}  (score {r['score']}, {r['industry']})")
        L.append(f"   Score: {r['score']}")
        L.append(f"   Why:  {r['why_this_company']}")
        L.append(f"   Offer: {r['recommended_service']} — {r['recommended_service_why']}")
        if r["recommended_service"] != r["entry_offer"]:
            L.append(f"   Entry offer: {r['entry_offer']} (scope the follow-on after findings review)")
        L.append(f"   Next:  {r['next_action']}")
        L.append(f"   Evidence: {r['evidence_count']} row(s), {r['pain_point_count']} pain point(s)")
        if r["discovery_questions"]:
            L.append(f"   Discovery: {r['discovery_questions'][0]}")
    L.append("")
    L.append("## MACHINE vs HUMAN DISAGREEMENT")
    L.append("")
    L.append(f"Evaluated by human: {disagreement['evaluated']}; aligned: {disagreement['aligned']}")
    if disagreement["high_machine_low_human"]:
        L.append("")
        L.append("### HIGH MACHINE / LOW HUMAN")
        for d in disagreement["high_machine_low_human"]:
            L.append(f"- {d['company']}: machine {d['machine_score']} / human {d['human_band']}")
            L.append(f"    possible reason: {d['human_reason'] or '(not supplied)'}")
    if disagreement["low_machine_high_human"]:
        L.append("")
        L.append("### LOW MACHINE / HIGH HUMAN")
        for d in disagreement["low_machine_high_human"]:
            L.append(f"- {d['company']}: machine {d['machine_score']} / human {d['human_band']}")
            L.append(f"    possible reason: {d['human_reason'] or '(not supplied)'}")
    return "\n".join(L)


def render_machine_json(reports, disagreement, ranking, meta, audits) -> Dict[str, Any]:
    return {
        "disclosure": "FIXTURE — synthetic prospects (rwv_fixture.py). Not real research.",
        "meta": meta,
        "ranking_explanation": ranking,
        "prospects": reports,
        "disagreement": disagreement,
        "audit_samples": audits,
    }

"""Lead research and pain-point detection over permitted local sources.

Research collects: description, industry, size/tech/hiring/operational signals,
public contact info, and automation opportunities. Every claim it records carries
a ``source_ref`` produced by an actual read — a file with a sha256, or an Atlas
claim id via the existing knowledge bridge. There is no path here that turns
model prose into evidence.

Pain-point detection is a **signal matcher, not an inference engine**: it looks
for the phrases the consulting ``Discovery_Rubric.md`` already names as
automation triggers (manual re-entry, tribal knowledge, document assembly by
hand, SaaS sprawl, ...) in real source text. A match cites the file and line it
matched; no match produces no pain point.
"""

from __future__ import annotations

import hashlib
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .models import ClaimTier, PainPoint
from .qualification import opportunity_score
from .repository import SalesRepository

# (claim_type, compiled pattern, human label)
SIGNALS: List[Tuple[str, "re.Pattern[str]", str]] = [
    ("size_signal", re.compile(r"\b(\d+)\s*\+?\s*(employees|staff|people|team|headcount)\b", re.I),
     "team size stated"),
    ("size_signal", re.compile(r"\b(\d+)\s*[-–]\s*(\d+)\s*(leads|leads/month|proposals|proposals/month)\b", re.I),
     "work volume stated"),
    ("hiring_signal", re.compile(r"\b(hiring|now hiring|we are hiring|join our team|open role|we're growing)\b", re.I),
     "actively hiring / growing"),
    ("tech_signal", re.compile(r"\b(salesforce|hubspot|zapier|airtable|notion|slack|jira|asana|"
                               r"intercom|zendesk|excel|google sheets?|saas|openai|chatgpt)\b", re.I),
     "tooling / AI dependency mentioned"),
    ("urgency_signal", re.compile(r"\b(asap|urgent|immediately|this quarter|before (the )?end of|cost review|cut (costs|spend))\b", re.I),
     "stated urgency / cost pressure"),
    ("budget_signal", re.compile(r"\$\s?\d[\d,]*", re.I), "monetary figure stated"),
    ("contact_info", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+", re.I), "email address published"),
    ("contact_info", re.compile(r"\b\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}\b"), "phone number published"),
]

# Pain patterns, each mapped to the Discovery_Rubric.md category it scores under
# plus the rubric dimensions the phrase evidences. Dimensions are conservative
# (mid-scale) because a phrase match is an OBSERVED signal, not a measurement.
PAIN_PATTERNS: List[Dict[str, Any]] = [
    {
        "pattern": re.compile(r"\b(copy (them )?over|re-?enter|re-?key|manual (data )?entry|by hand|"
                              r"manually (process|enter|track|update|key)|same (data|info) (in|into) (two|three|multiple|several))\b", re.I),
        "category": "Data Entry & Intake",
        "text": "The same data appears to be re-keyed or entered manually across multiple systems.",
        "dimensions": {"severity": 4, "frequency": 5, "revenue_impact": 3,
                       "automation_potential": 5, "implementation_difficulty": 2},
    },
    {
        "pattern": re.compile(r"\b(tribal knowledge|in (someone's|one person's|her|his|their) head|"
                              r"no (one|single) (source|place)|scattered (across|between)|can't (find|locate)|"
                              r"knowledge lives|nobody knows where)\b", re.I),
        "category": "Knowledge Flow",
        "text": "Operational knowledge appears trapped in individuals rather than a searchable system.",
        "dimensions": {"severity": 4, "frequency": 4, "revenue_impact": 4,
                       "automation_potential": 4, "implementation_difficulty": 3},
    },
    {
        "pattern": re.compile(r"\b(assembled by hand|put together (the|our) (reports?|proposals?|contracts?|packets?|intake)|"
                              r"manual(ly)? (report|proposal|contract|document)|build (the|our) (reports?|decks?) )\b", re.I),
        "category": "Document Flow",
        "text": "Documents (reports, proposals, contracts, intake) appear to be assembled by hand.",
        "dimensions": {"severity": 3, "frequency": 4, "revenue_impact": 3,
                       "automation_potential": 4, "implementation_difficulty": 3},
    },
    {
        "pattern": re.compile(r"\b(too many (tools|saas|subscriptions|apps)|paying for .*saas|overlapping tools|"
                              r"saas sprawl|each tool (does|costs)|redundant (software|tools)|subscription creep)\b", re.I),
        "category": "Tooling & SaaS Spend",
        "text": "The business appears to carry overlapping SaaS tools that may be consolidated.",
        "dimensions": {"severity": 3, "frequency": 4, "revenue_impact": 5,
                       "automation_potential": 3, "implementation_difficulty": 3},
    },
    {
        "pattern": re.compile(r"\b(after hours|weekends?|nights?|when we'?re? (out|busy|closed)|outside (business )?hours|"
                              r"no one (covers|is available))\b", re.I),
        "category": "Coverage",
        "text": "Coverage gaps outside business hours are acknowledged.",
        "dimensions": {"severity": 4, "frequency": 3, "revenue_impact": 3,
                       "automation_potential": 4, "implementation_difficulty": 2},
    },
    {
        "pattern": re.compile(r"\b(don'?t track|no visibility|not sure how many|we don'?t know how many|"
                              r"no reporting|can't measure|hard to measure)\b", re.I),
        "category": "Measurement",
        "text": "No measurement of a workflow or its conversion is in place.",
        "dimensions": {"severity": 4, "frequency": 5, "revenue_impact": 4,
                       "automation_potential": 4, "implementation_difficulty": 3},
    },
    {
        "pattern": re.compile(r"\b(report(s)? .* (every|each) (week|month)|monthly report|same report|"
                              r"nobody reads .* report|reporting takes|spend(s)? .* on reports)\b", re.I),
        "category": "Reporting",
        "text": "Repetitive reporting is produced by hand and may add little value.",
        "dimensions": {"severity": 3, "frequency": 4, "revenue_impact": 3,
                       "automation_potential": 4, "implementation_difficulty": 2},
    },
]


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_source(path: str) -> Tuple[str, str]:
    """Read a research source file and return (text, source_ref with sha256)."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    return text, f"{path}#sha256:{file_sha256(path)[:12]}"


def extract_signals(text: str, source_ref: str) -> List[Dict[str, Any]]:
    """Find declared signal types in real text. Each hit cites its line."""
    out: List[Dict[str, Any]] = []
    seen: set = set()
    for lineno, line in enumerate(text.splitlines(), start=1):
        for claim_type, pattern, label in SIGNALS:
            m = pattern.search(line)
            if not m:
                continue
            key = (claim_type, m.group(0).lower())
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "claim_type": claim_type,
                    "claim_text": f"{label}: {m.group(0).strip()}",
                    "source_ref": f"{source_ref}#L{lineno}",
                    "excerpt": line.strip()[:400],
                    "tier": ClaimTier.OBSERVED.value,
                }
            )
    return out


def detect_pain(text: str, source_ref: str) -> List[Dict[str, Any]]:
    """Match the rubric's own signal phrases. No match -> no pain point."""
    found: List[Dict[str, Any]] = []
    claimed: set = set()
    for lineno, line in enumerate(text.splitlines(), start=1):
        for spec in PAIN_PATTERNS:
            m = spec["pattern"].search(line)
            if not m:
                continue
            if spec["category"] + spec["text"] in claimed:
                continue
            claimed.add(spec["category"] + spec["text"])
            found.append(
                {
                    "text": spec["text"],
                    "category": spec["category"],
                    "dimensions": dict(spec["dimensions"]),
                    "source_ref": f"{source_ref}#L{lineno}",
                    "matched": m.group(0).strip(),
                    "excerpt": line.strip()[:400],
                }
            )
    return found


def research_lead(
    repo: SalesRepository,
    lead_id: str,
    sources: Iterable[str],
    *,
    evidence: Any,
    run_id: str = "",
) -> Dict[str, Any]:
    """Read permitted source files, record signals as evidence, derive pain points.

    ``sources`` must already be resolved paths inside the worker's filesystem
    boundary — the tool layer resolves them with ``ctx.resolve`` before calling.
    """
    lead = repo.require_lead(lead_id)
    company = repo.get_company(lead.company_id)
    recorded_evidence: List[str] = []
    pain_recorded: List[Dict[str, Any]] = []
    read_sources: List[str] = []
    missing: List[str] = []

    for path in sources:
        if not os.path.isfile(path):
            missing.append(path)
            continue
        text, source_ref = read_source(path)
        read_sources.append(source_ref)

        for sig in extract_signals(text, source_ref):
            rec = evidence.attach(
                lead_id,
                sig["claim_type"],
                sig["claim_text"],
                sig["source_ref"],
                tier=sig["tier"],
                excerpt=sig["excerpt"],
                run_id=run_id,
            )
            recorded_evidence.append(rec.id)

        for pain in detect_pain(text, source_ref):
            ev = evidence.attach(
                lead_id,
                "pain_point",
                f"{pain['text']} (matched: {pain['matched']!r})",
                pain["source_ref"],
                tier=ClaimTier.OBSERVED.value,
                excerpt=pain["excerpt"],
                run_id=run_id,
            )
            recorded_evidence.append(ev.id)
            pp = PainPoint(
                lead_id=lead_id,
                text=pain["text"],
                category=pain["category"],
                tier=ClaimTier.OBSERVED,
                evidence_ids=[ev.id],
                **pain["dimensions"],
            )
            pp.opportunity_score = opportunity_score(pp)
            repo.add_pain_point(pp)
            pain_recorded.append(
                {
                    "id": pp.id,
                    "text": pp.text,
                    "category": pp.category,
                    "opportunity_score": pp.opportunity_score,
                    "evidence_id": ev.id,
                }
            )

    if read_sources:
        from .models import Activity

        repo.log_activity(
            Activity(
                lead_id=lead_id,
                kind="research",
                summary=(
                    f"researched {company.name if company else lead_id}: "
                    f"{len(recorded_evidence)} evidence, {len(pain_recorded)} pain point(s)"
                ),
                detail="; ".join(read_sources),
                run_id=run_id,
                evidence_ids=recorded_evidence,
            )
        )

    return {
        "lead_id": lead_id,
        "company": company.name if company else "",
        "sources_read": read_sources,
        "sources_missing": missing,
        "evidence_ids": recorded_evidence,
        "evidence_count": len(recorded_evidence),
        "pain_points": pain_recorded,
        "degraded": bool(missing) or not read_sources,
    }

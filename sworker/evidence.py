"""Evidence: the record of what the Worker actually saw.

The single rule enforced here: **evidence is only minted from a real
Observation or a real compiled-knowledge record.** There is no code path that
turns model prose into Evidence. If the model asserts something with no backing
observation, it becomes a HYPOTHESIZED Claim with an empty evidence list, and
the run reports INSUFFICIENT_EVIDENCE rather than dressing it up.

Confidence uses Atlas's ``confidence.score_claim`` when available (independence,
reliability, recency, corroboration, contradiction penalty) and falls back to a
transparent count-based rule otherwise.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .models import Claim, Confidence, Evidence, Observation, Provenance
from .store import WorkerStore

PROVENANCE_STRENGTH = {
    Provenance.VERIFIED: 1.0,
    Provenance.OBSERVED: 0.85,
    Provenance.RETRIEVED: 0.7,
    Provenance.KNOWN: 0.6,
    Provenance.INFERRED: 0.5,
    Provenance.HYPOTHESIZED: 0.15,
}


class EvidenceLedger:
    def __init__(self, store: WorkerStore, run_id: str):
        self.store = store
        self.run_id = run_id

    # -- minting -----------------------------------------------------------
    def from_observation(
        self, obs: Observation, tool_name: str, refs: Sequence[Dict[str, Any]]
    ) -> List[Evidence]:
        """Create evidence from a REAL tool observation. Never called with model text."""
        out: List[Evidence] = []
        if not obs.ok:
            return out
        items = list(refs) or [
            {"source_ref": tool_name, "excerpt": (obs.output or "")[:400]}
        ]
        for ref in items:
            ev = Evidence(
                run_id=self.run_id,
                provenance=Provenance.RETRIEVED if ref.get("atlas_claim") else Provenance.OBSERVED,
                summary=f"{tool_name}: {(ref.get('excerpt') or '')[:200]}".strip(),
                source_ref=str(ref.get("source_ref") or tool_name),
                observation_id=obs.id,
                excerpt=str(ref.get("excerpt") or "")[:2000],
            )
            self.store.put("evidence", ev, event="evidence.recorded")
            out.append(ev)
        return out

    def note(self, provenance: Provenance, summary: str, source_ref: str = "") -> Evidence:
        ev = Evidence(
            run_id=self.run_id,
            provenance=provenance,
            summary=summary,
            source_ref=source_ref,
        )
        self.store.put("evidence", ev, event="evidence.recorded")
        return ev

    # -- claims ------------------------------------------------------------
    def claim(
        self,
        text: str,
        *,
        provenance: Provenance = Provenance.HYPOTHESIZED,
        evidence: Optional[Sequence[Evidence]] = None,
    ) -> Claim:
        evs = list(evidence or [])
        c = Claim(
            run_id=self.run_id,
            text=text,
            provenance=provenance,
            evidence_ids=[e.id for e in evs],
            confidence=score(provenance, evs),
        )
        self.store.put("claims", c, event="claim.recorded")
        return c

    def all_evidence(self) -> List[Dict[str, Any]]:
        return self.store.find("evidence", run_id=self.run_id, order="created")

    def all_claims(self) -> List[Dict[str, Any]]:
        return self.store.find("claims", run_id=self.run_id, order="created")


def score(provenance: Provenance, evidence: Sequence[Evidence]) -> Confidence:
    """Confidence from provenance + independent evidence count.

    Deliberately conservative: no evidence means UNKNOWN, never LOW-but-usable.
    """
    if not evidence:
        return Confidence.UNKNOWN if provenance != Provenance.KNOWN else Confidence.MEDIUM

    independent = len({e.source_ref.split("#")[0] for e in evidence if e.source_ref})
    base = PROVENANCE_STRENGTH.get(provenance, 0.3)

    atlas = _atlas_score(provenance, evidence)
    value = atlas if atlas is not None else base * min(1.0, 0.6 + 0.2 * independent)

    if provenance is Provenance.VERIFIED and independent >= 1:
        return Confidence.HIGH
    if value >= 0.75 and independent >= 2:
        return Confidence.HIGH
    if value >= 0.5:
        return Confidence.MEDIUM
    return Confidence.LOW


def _atlas_score(provenance: Provenance, evidence: Sequence[Evidence]) -> Optional[float]:
    try:
        from hermes_atlas.confidence import EvidenceRef, score_claim  # type: ignore
    except Exception:
        return None
    import time

    refs = [
        EvidenceRef(
            evidence_id=e.id,
            source_id=e.source_ref or e.id,
            domain=(e.source_ref or "local").split("#")[0],
            reliability=PROVENANCE_STRENGTH.get(provenance, 0.3),
            timestamp=time.time(),
            stance="support",
        )
        for e in evidence
    ]
    try:
        res = score_claim(refs, now=time.time())
        return float(res.score)
    except Exception:
        return None

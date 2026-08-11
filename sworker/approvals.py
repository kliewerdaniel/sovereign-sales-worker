"""The approval primitive.

An approval is a durable record, not a prompt. The engine creates it, persists
it, and stops. Something else — a human at the CLI, or the web UI — decides.
The decision is appended to the audit trail and can never be edited.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import (
    Action,
    ActionStatus,
    Approval,
    ApprovalState,
    RiskLevel,
    now,
)
from .store import WorkerStore


class ApprovalManager:
    def __init__(self, store: WorkerStore):
        self.store = store

    # -- creation ----------------------------------------------------------
    def request(
        self,
        action: Action,
        *,
        summary: str,
        reason: str,
        evidence_ids: Optional[List[str]] = None,
    ) -> Approval:
        appr = Approval(
            run_id=action.run_id,
            action_id=action.id,
            risk=action.risk,
            summary=summary,
            reason=reason,
            evidence_ids=list(evidence_ids or []),
        )
        self.store.put("approvals", appr, event="approval.requested")
        action.approval_id = appr.id
        action.status = ActionStatus.AWAITING_APPROVAL
        self.store.put("actions", action, event="action.awaiting_approval")
        return appr

    # -- decisions ---------------------------------------------------------
    def _decide(
        self, approval_id: str, state: ApprovalState, who: str, note: str
    ) -> Dict[str, Any]:
        rec = self.store.get("approvals", approval_id)
        if rec is None:
            raise KeyError(f"no approval {approval_id!r}")
        if rec["state"] != ApprovalState.PENDING.value:
            raise ValueError(
                f"approval {approval_id} is already {rec['state']}; approvals are immutable"
            )
        rec["state"] = state.value
        rec["decided_by"] = who
        rec["decided_at"] = now()
        rec["note"] = note
        self.store.put("approvals", rec, event=f"approval.{state.value.lower()}")

        act = self.store.get("actions", rec["action_id"])
        if act:
            act["status"] = (
                ActionStatus.APPROVED.value
                if state is ApprovalState.APPROVED
                else ActionStatus.REJECTED.value
            )
            self.store.put("actions", act, event="action.decided")
        return rec

    def approve(self, approval_id: str, who: str = "cli", note: str = "") -> Dict[str, Any]:
        return self._decide(approval_id, ApprovalState.APPROVED, who, note)

    def reject(self, approval_id: str, who: str = "cli", note: str = "") -> Dict[str, Any]:
        return self._decide(approval_id, ApprovalState.REJECTED, who, note)

    def decide(self, approval_id: str, *, approved: bool, by: str = "cli", note: str = "") -> Dict[str, Any]:
        return self._decide(
            approval_id,
            ApprovalState.APPROVED if approved else ApprovalState.REJECTED,
            by,
            note,
        )

    # -- queries -----------------------------------------------------------
    def pending(self, run_id: str = "") -> List[Dict[str, Any]]:
        if run_id:
            return self.store.find(
                "approvals", order="created", state=ApprovalState.PENDING.value, run_id=run_id
            )
        return self.store.find("approvals", order="created", state=ApprovalState.PENDING.value)

    def for_run(self, run_id: str) -> List[Dict[str, Any]]:
        return self.store.find("approvals", run_id=run_id, order="created")

    def get(self, approval_id: str) -> Optional[Dict[str, Any]]:
        return self.store.get("approvals", approval_id)

    def resolve_ref(self, ref: str) -> Optional[Dict[str, Any]]:
        """Accept a full approval id, an action id, or a unique id prefix."""
        rec = self.store.get("approvals", ref)
        if rec:
            return rec
        by_action = self.store.find("approvals", action_id=ref)
        if by_action:
            return by_action[0]
        matches = [a for a in self.store.find("approvals") if a["id"].startswith(ref)]
        return matches[0] if len(matches) == 1 else None


def render_request(approval: Dict[str, Any], evidence: List[Dict[str, Any]]) -> str:
    lines = [
        "ACTION REQUIRES APPROVAL",
        "",
        "Action:",
        f"  {approval['summary']}",
        "",
        "Reason:",
        f"  {approval['reason']}",
        "",
        "Risk:",
        f"  {approval['risk'].upper()}",
    ]
    if evidence:
        lines += ["", "Evidence:"]
        for e in evidence:
            lines.append(f"  - [{e['provenance']}] {e['summary']}")
            if e.get("source_ref"):
                lines.append(f"      source: {e['source_ref']}")
    lines += [
        "",
        f"  approve:  worker approve {approval['id']}",
        f"  reject:   worker reject  {approval['id']}",
    ]
    return "\n".join(lines)

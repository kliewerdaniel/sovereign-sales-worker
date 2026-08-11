"""Risk classification and the permission decision.

Two rules do the real work here:

1. **The tool's declared risk is a floor, not a suggestion.** The engine asks
   this module; the model is never consulted about whether something is risky.

2. **Decomposition does not launder risk.** An agent denied "send the email" must
   not get there by proposing "write the email to a file" then "shell: sendmail".
   ``DecompositionGuard`` tracks the risk ceiling that has already been refused
   or is pending within a run, and blocks equal-or-higher-risk actions from
   sneaking through afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .config import WorkerConfig
from .models import Action, RiskLevel, risk_rank


@dataclass
class Decision:
    allowed: bool                 # may proceed without a human right now
    needs_approval: bool
    risk: RiskLevel
    reason: str
    denied: bool = False          # policy refusal; no human will be asked


def classify(tool, args: Dict[str, Any]) -> RiskLevel:
    """Effective risk for a concrete invocation.

    Context can only ever RAISE risk except for the one documented downgrade:
    an HTTP GET against localhost is not an external action (nothing leaves the
    machine), so it drops to READ.
    """
    risk = tool.risk
    if tool.name == "http.get":
        from .tools.http import risk_for_url

        risk = risk_for_url(str(args.get("url", "")))
    if tool.name == "shell.exec":
        cmd = str(args.get("command", "")).lower()
        if any(tok in cmd.split() for tok in ("rm", "rmdir", "shred", "dd", "mkfs")):
            risk = RiskLevel.DESTRUCTIVE
        elif any(tok in cmd for tok in ("curl ", "wget ", "ssh ", "scp ", "nc ")):
            risk = RiskLevel.EXTERNAL
    if tool.name == "python.run":
        code = str(args.get("code", ""))
        if any(tok in code for tok in ("shutil.rmtree", "os.remove", "os.unlink")):
            risk = RiskLevel.DESTRUCTIVE
        elif any(tok in code for tok in ("urllib.request", "requests.", "socket.", "httpx")):
            risk = RiskLevel.EXTERNAL
    return risk


class DecompositionGuard:
    """Per-run memory of refused/pending risk ceilings."""

    def __init__(self):
        self.refused: Set[str] = set()       # risk values a human rejected
        self.pending: Set[str] = set()       # risk values awaiting a decision
        self.notes: List[str] = []

    def record_rejection(self, risk: RiskLevel) -> None:
        self.refused.add(RiskLevel(risk).value)

    def record_pending(self, risk: RiskLevel) -> None:
        self.pending.add(RiskLevel(risk).value)

    def clear_pending(self, risk: RiskLevel) -> None:
        self.pending.discard(RiskLevel(risk).value)

    def blocked_reason(self, risk: RiskLevel) -> Optional[str]:
        rank = risk_rank(risk)
        for refused in self.refused:
            if risk_rank(refused) <= rank and risk_rank(risk) > risk_rank(RiskLevel.REVERSIBLE):
                return (
                    f"a {refused.upper()} action was already rejected in this run; refusing an "
                    f"equal-or-higher-risk {RiskLevel(risk).value.upper()} action rather than "
                    "letting the task be decomposed around the rejection"
                )
        return None


class PermissionEngine:
    def __init__(self, worker: WorkerConfig, guard: Optional[DecompositionGuard] = None):
        self.worker = worker
        self.guard = guard or DecompositionGuard()

    def evaluate(self, tool, args: Dict[str, Any]) -> Decision:
        risk = classify(tool, args)
        policy = self.worker.policy_for(risk)

        blocked = self.guard.blocked_reason(risk)
        if blocked:
            return Decision(False, False, risk, blocked, denied=True)

        if policy == "deny":
            return Decision(
                False,
                False,
                risk,
                f"worker policy denies all {risk.value.upper()} actions",
                denied=True,
            )

        if getattr(tool, "requires_approval", False):
            return Decision(
                False,
                True,
                risk,
                f"tool {tool.name!r} always requires approval ({risk.value.upper()})",
            )

        if policy == "approve":
            return Decision(
                False,
                True,
                risk,
                f"worker policy requires approval for {risk.value.upper()} actions",
            )

        return Decision(True, False, risk, f"{risk.value.upper()} is automatic under worker policy")

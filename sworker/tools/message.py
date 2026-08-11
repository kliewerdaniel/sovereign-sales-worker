"""Messaging abstraction. Slack is NOT a dependency — it is one possible adapter.

The default backend writes the message to an outbox file. That is not a fake
integration pretending to be Slack: the tool reports exactly what it did
("queued to outbox"), and the artifact is a real file you can inspect.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional, Protocol

from ..models import RiskLevel
from .base import Tool, ToolContext, ToolResult


class MessageBackend(Protocol):
    name: str

    def available(self) -> bool: ...

    def send(self, channel: str, text: str, ctx: Any) -> Dict[str, Any]: ...


class OutboxBackend:
    """Writes to <workspace>/artifacts/outbox.jsonl. Local, inspectable, honest."""

    name = "outbox"

    def available(self) -> bool:
        return True

    def send(self, channel: str, text: str, ctx: ToolContext) -> Dict[str, Any]:
        path = os.path.join(ctx.artifacts_dir, "outbox.jsonl")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        rec = {
            "ts": time.time(),
            "run_id": ctx.run_id,
            "worker": ctx.worker,
            "channel": channel,
            "text": text,
            "delivered": False,
            "note": "queued locally; no external service was contacted",
        }
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
        return {"outbox": path, **rec}


_backend: MessageBackend = OutboxBackend()


def set_backend(backend: MessageBackend) -> None:
    global _backend
    _backend = backend


def get_backend() -> MessageBackend:
    return _backend


class SendMessage(Tool):
    name = "message.send"
    description = (
        "Send a message to a channel via the configured messaging backend. "
        "Default backend queues to a local outbox; nothing leaves the machine."
    )
    risk = RiskLevel.EXTERNAL
    reversible = False
    requires_approval = True
    input_schema = {
        "type": "object",
        "properties": {"channel": {"type": "string"}, "text": {"type": "string"}},
        "required": ["channel", "text"],
    }

    def summarize(self, args: Dict[str, Any]) -> str:
        preview = (args.get("text") or "")[:120].replace("\n", " ")
        return f"send message to {args.get('channel')!r} via {_backend.name}: {preview!r}"

    def run(self, ctx: ToolContext, args: Dict[str, Any]) -> ToolResult:
        if not _backend.available():
            return ToolResult(False, error=f"message backend {_backend.name!r} unavailable")
        info = _backend.send(args["channel"], args["text"], ctx)
        return ToolResult(
            True,
            output=f"message queued to {args['channel']} via {_backend.name}",
            data=info,
        )


TOOLS = [SendMessage()]

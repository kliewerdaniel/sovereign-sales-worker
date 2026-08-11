"""HTTP tool. Network egress is a boundary crossing, so it is EXTERNAL risk
for anything that is not a plain GET to an allowlisted host."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict

from ..models import RiskLevel
from .base import Tool, ToolContext, ToolError, ToolResult, truncate

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def _request(method: str, url: str, ctx: ToolContext, args: Dict[str, Any]) -> ToolResult:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ToolError(f"unsupported URL scheme: {parsed.scheme!r}")
    headers = dict(args.get("headers") or {})
    auth = args.get("auth_env")
    if auth:
        import os

        if auth not in ctx.env_allow:
            raise ToolError(
                f"auth_env {auth!r} is not in this worker's env_allow list; refusing to "
                "read an undeclared credential"
            )
        token = os.environ.get(auth)
        if not token:
            return ToolResult(False, error=f"env var {auth} is not set")
        headers["Authorization"] = f"Bearer {token}"
    body = None
    if args.get("body") is not None:
        raw = args["body"]
        body = (raw if isinstance(raw, str) else json.dumps(raw)).encode()
        headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=min(int(args.get("timeout", 30)), 120)) as r:
            text = r.read().decode("utf-8", errors="replace")
            status = r.status
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        status = exc.code
    except Exception as exc:
        return ToolResult(False, error=f"{type(exc).__name__}: {exc}", data={"url": url})
    out, trunc = truncate(text, ctx.max_output)
    parsed_body = None
    try:
        parsed_body = json.loads(text)
    except Exception:
        pass
    ok = 200 <= status < 400
    return ToolResult(
        ok,
        output=f"HTTP {status}\n{out}",
        error="" if ok else f"HTTP {status}",
        truncated=trunc,
        data={"url": url, "status": status, "json": parsed_body},
        evidence=[{"source_ref": url, "excerpt": out[:400]}],
    )


class HttpGet(Tool):
    name = "http.get"
    description = "HTTP GET. Local hosts are READ risk; remote hosts are EXTERNAL."
    risk = RiskLevel.EXTERNAL
    input_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "headers": {"type": "object", "default": {}},
            "auth_env": {"type": "string"},
            "timeout": {"type": "integer", "default": 30},
        },
        "required": ["url"],
    }

    def summarize(self, args: Dict[str, Any]) -> str:
        return f"HTTP GET {args.get('url')}"

    def run(self, ctx: ToolContext, args: Dict[str, Any]) -> ToolResult:
        return _request("GET", args["url"], ctx, args)


class HttpPost(Tool):
    name = "http.post"
    description = "HTTP POST with a JSON body. Always EXTERNAL risk."
    risk = RiskLevel.EXTERNAL
    reversible = False
    input_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "body": {"type": "object"},
            "headers": {"type": "object", "default": {}},
            "auth_env": {"type": "string"},
            "timeout": {"type": "integer", "default": 30},
        },
        "required": ["url"],
    }

    def summarize(self, args: Dict[str, Any]) -> str:
        return f"HTTP POST {args.get('url')} (sends data off this machine)"

    def run(self, ctx: ToolContext, args: Dict[str, Any]) -> ToolResult:
        return _request("POST", args["url"], ctx, args)


def risk_for_url(url: str) -> RiskLevel:
    """A GET against localhost is not an external action. Used by the engine to
    downgrade risk for local-only endpoints."""
    host = urllib.parse.urlparse(url).hostname or ""
    return RiskLevel.READ if host in LOCAL_HOSTS else RiskLevel.EXTERNAL


TOOLS = [HttpGet(), HttpPost()]

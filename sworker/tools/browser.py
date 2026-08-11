"""Browser abstraction.

No browser driver is a dependency of the core. This module defines the *port*
(``BrowserBackend``) so a Playwright/CDP/computer-use adapter can be dropped in
later without touching the engine, plus a ``NullBrowser`` that fails honestly.

A tool that cannot do its job returns ok=False with a real reason. It does NOT
return plausible-looking fake page text — a fake integration that makes the demo
look complete is worse than a missing one.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Protocol

from ..models import RiskLevel
from .base import Tool, ToolContext, ToolResult, truncate


class BrowserBackend(Protocol):
    name: str

    def available(self) -> bool: ...

    def open(self, url: str, timeout: int = 30) -> Dict[str, Any]: ...

    def text(self) -> str: ...

    def click(self, selector: str) -> Dict[str, Any]: ...

    def type(self, selector: str, text: str) -> Dict[str, Any]: ...

    def screenshot(self, path: str) -> str: ...


class NullBrowser:
    """The default backend: honest about not existing."""

    name = "null"

    def available(self) -> bool:
        return False

    def _fail(self):
        raise RuntimeError(
            "no browser backend is configured. Install one and register it with "
            "sworker.tools.browser.set_backend(); the core deliberately ships without "
            "a browser dependency."
        )

    def open(self, url: str, timeout: int = 30):
        self._fail()

    def text(self) -> str:
        self._fail()
        return ""

    def click(self, selector: str):
        self._fail()

    def type(self, selector: str, text: str):
        self._fail()

    def screenshot(self, path: str) -> str:
        self._fail()
        return ""


_backend: BrowserBackend = NullBrowser()


def set_backend(backend: BrowserBackend) -> None:
    global _backend
    _backend = backend


def get_backend() -> BrowserBackend:
    return _backend


class _BrowserTool(Tool):
    def _guard(self) -> Optional[ToolResult]:
        if not _backend.available():
            return ToolResult(
                False,
                error=(
                    f"browser backend {_backend.name!r} is not available. "
                    "No page was fetched and no content is being reported."
                ),
                data={"backend": _backend.name},
            )
        return None


class BrowserOpen(_BrowserTool):
    name = "browser.open"
    description = "Open a URL in the configured browser backend and return page text."
    risk = RiskLevel.EXTERNAL
    input_schema = {
        "type": "object",
        "properties": {"url": {"type": "string"}, "timeout": {"type": "integer", "default": 30}},
        "required": ["url"],
    }

    def summarize(self, args):
        return f"open browser at {args.get('url')}"

    def run(self, ctx: ToolContext, args: Dict[str, Any]) -> ToolResult:
        bad = self._guard()
        if bad:
            return bad
        meta = _backend.open(args["url"], int(args.get("timeout", 30)))
        text, trunc = truncate(_backend.text(), ctx.max_output)
        return ToolResult(
            True,
            output=text,
            truncated=trunc,
            data={"url": args["url"], **(meta or {})},
            evidence=[{"source_ref": args["url"], "excerpt": text[:400]}],
        )


class BrowserClick(_BrowserTool):
    name = "browser.click"
    description = "Click an element in the open page. Consequential: EXTERNAL."
    risk = RiskLevel.EXTERNAL
    reversible = False
    input_schema = {
        "type": "object",
        "properties": {"selector": {"type": "string"}},
        "required": ["selector"],
    }

    def run(self, ctx, args):
        bad = self._guard()
        if bad:
            return bad
        return ToolResult(True, data=_backend.click(args["selector"]) or {})


class BrowserType(_BrowserTool):
    name = "browser.type"
    description = "Type into an element in the open page."
    risk = RiskLevel.EXTERNAL
    reversible = False
    input_schema = {
        "type": "object",
        "properties": {"selector": {"type": "string"}, "text": {"type": "string"}},
        "required": ["selector", "text"],
    }

    def run(self, ctx, args):
        bad = self._guard()
        if bad:
            return bad
        return ToolResult(True, data=_backend.type(args["selector"], args["text"]) or {})


TOOLS = [BrowserOpen(), BrowserClick(), BrowserType()]

"""Built-in tool registry."""

from __future__ import annotations

from .base import Tool, ToolContext, ToolError, ToolRegistry, ToolResult, truncate  # noqa: F401
from . import browser, data, exec as exec_tools, fs, git, http, knowledge, message


def build_registry() -> ToolRegistry:
    r = ToolRegistry()
    for module in (fs, data, exec_tools, http, git, browser, message, knowledge):
        for tool in module.TOOLS:
            r.register(tool)
    return r


DEFAULT_REGISTRY = build_registry()

__all__ = [
    "Tool",
    "ToolContext",
    "ToolError",
    "ToolRegistry",
    "ToolResult",
    "build_registry",
    "DEFAULT_REGISTRY",
    "truncate",
]

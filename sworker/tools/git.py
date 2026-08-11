"""Git tools. Read operations are free; commits are reversible; push is external
(leaves the machine). See docs/SECURITY.md (section 4) for the egress caveats.
"""

from __future__ import annotations

import os
import subprocess
from typing import Any, Dict, List

from ..models import RiskLevel
from .base import Tool, ToolContext, ToolError, ToolResult, truncate


def _git(ctx: ToolContext, repo: str, argv: List[str], timeout: int = 30) -> ToolResult:
    path = ctx.resolve(repo, must_exist=True)
    if not os.path.isdir(os.path.join(path, ".git")):
        return ToolResult(False, error=f"{repo} is not a git repository")
    try:
        proc = subprocess.run(
            ["git", *argv],
            cwd=path,
            env=ctx.clean_env(),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return ToolResult(False, error="git is not installed")
    except subprocess.TimeoutExpired:
        return ToolResult(False, error=f"git timed out after {timeout}s")
    out, trunc = truncate((proc.stdout + proc.stderr).strip(), ctx.max_output)
    ok = proc.returncode == 0
    return ToolResult(
        ok,
        output=out,
        error="" if ok else f"git exit {proc.returncode}",
        truncated=trunc,
        data={"repo": path, "argv": argv, "exit_code": proc.returncode},
    )


class GitStatus(Tool):
    name = "git.status"
    description = "Show git status --short for a repository in the boundary."
    risk = RiskLevel.READ
    input_schema = {"type": "object", "properties": {"repo": {"type": "string", "default": "."}}}

    def run(self, ctx, args):
        return _git(ctx, args.get("repo", "."), ["status", "--short", "--branch"])


class GitDiff(Tool):
    name = "git.diff"
    description = "Show a git diff (optionally --staged)."
    risk = RiskLevel.READ
    input_schema = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "default": "."},
            "staged": {"type": "boolean", "default": False},
            "path": {"type": "string", "default": ""},
        },
    }

    def run(self, ctx, args):
        argv = ["diff"]
        if args.get("staged"):
            argv.append("--staged")
        if args.get("path"):
            argv += ["--", args["path"]]
        return _git(ctx, args.get("repo", "."), argv)


class GitBranch(Tool):
    name = "git.branch"
    description = "Create or list branches. Creating a branch is reversible."
    risk = RiskLevel.REVERSIBLE
    input_schema = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "default": "."},
            "name": {"type": "string", "default": ""},
        },
    }

    def run(self, ctx, args):
        name = args.get("name") or ""
        argv = ["checkout", "-b", name] if name else ["branch", "--list"]
        return _git(ctx, args.get("repo", "."), argv)


class GitCommit(Tool):
    name = "git.commit"
    description = "Stage given paths and commit. Reversible (history is retained)."
    risk = RiskLevel.REVERSIBLE
    input_schema = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "default": "."},
            "message": {"type": "string"},
            "paths": {"type": "array", "default": []},
        },
        "required": ["message"],
    }

    def summarize(self, args):
        return f"git commit in {args.get('repo', '.')}: {args.get('message')!r}"

    def run(self, ctx, args):
        repo = args.get("repo", ".")
        paths = args.get("paths") or ["-A"]
        add = _git(ctx, repo, ["add", *paths])
        if not add.ok:
            return add
        return _git(ctx, repo, ["commit", "-m", args["message"]])


class GitPush(Tool):
    name = "git.push"
    description = "Push to a remote. Leaves the machine — EXTERNAL, always approved."
    risk = RiskLevel.EXTERNAL
    reversible = False
    requires_approval = True
    input_schema = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "default": "."},
            "remote": {"type": "string", "default": "origin"},
            "branch": {"type": "string", "default": ""},
        },
    }

    def summarize(self, args):
        return f"git push {args.get('remote','origin')} {args.get('branch','')} (publishes off-machine)"

    def run(self, ctx, args):
        argv = ["push", args.get("remote", "origin")]
        if args.get("branch"):
            argv.append(args["branch"])
        return _git(ctx, args.get("repo", "."), argv, timeout=120)


TOOLS = [GitStatus(), GitDiff(), GitBranch(), GitCommit(), GitPush()]

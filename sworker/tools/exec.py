"""Shell + Python execution.

Honest security note: these run as SUBPROCESSES on the host, not in a VM. The
boundaries enforced are real but shallow — see docs/SECURITY.md (section 2) for
the full model and its limits, including why you should set ``sandbox: docker``
on a worker for genuine isolation rather than relying on these controls as a
security boundary.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List

from ..models import RiskLevel
from .base import Tool, ToolContext, ToolError, ToolResult, truncate


def _run_argv(argv: List[str], ctx: ToolContext, timeout: int) -> ToolResult:
    t0 = time.time()
    try:
        proc = subprocess.run(
            argv,
            cwd=ctx.workspace,
            env=ctx.clean_env(),
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except FileNotFoundError:
        return ToolResult(False, error=f"command not found: {argv[0]}")
    except subprocess.TimeoutExpired:
        return ToolResult(
            False,
            error=f"timed out after {timeout}s",
            data={"timeout": True, "argv": argv},
        )
    out, t1 = truncate(proc.stdout, ctx.max_output)
    err, t2 = truncate(proc.stderr, ctx.max_output)
    ok = proc.returncode == 0
    combined = out if not err else f"{out}\n[stderr]\n{err}"
    return ToolResult(
        ok,
        output=combined.strip(),
        error="" if ok else f"exit {proc.returncode}: {err.strip()[:500]}",
        truncated=t1 or t2,
        data={
            "argv": argv,
            "exit_code": proc.returncode,
            "stdout": out,
            "stderr": err,
            "duration_ms": int((time.time() - t0) * 1000),
        },
    )


class ShellExec(Tool):
    name = "shell.exec"
    description = (
        "Run an allowlisted command. Parsed with shlex and executed WITHOUT a shell, "
        "so pipes/redirection/globs are not interpreted."
    )
    risk = RiskLevel.REVERSIBLE
    permissions = ["subprocess"]
    input_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "timeout": {"type": "integer", "default": 30},
        },
        "required": ["command"],
    }

    def summarize(self, args: Dict[str, Any]) -> str:
        return f"run shell command: {args.get('command')}"

    def run(self, ctx: ToolContext, args: Dict[str, Any]) -> ToolResult:
        try:
            argv = shlex.split(args["command"])
        except ValueError as exc:
            raise ToolError(f"cannot parse command: {exc}") from exc
        if not argv:
            raise ToolError("empty command")
        if not ctx.shell_allow:
            raise ToolError(
                "this worker has no shell_allow list; shell execution is denied by default"
            )
        base = os.path.basename(argv[0])
        if base not in ctx.shell_allow and argv[0] not in ctx.shell_allow:
            raise ToolError(
                f"command {base!r} is not in this worker's shell_allow list {ctx.shell_allow}"
            )
        timeout = min(int(args.get("timeout", 30)), 300)
        return _run_argv(argv, ctx, timeout)


class PythonAnalysis(Tool):
    name = "python.run"
    description = (
        "Run a Python analysis script in the workspace. The script may print a line "
        "starting with 'RESULT_JSON:' followed by a JSON object; that object is captured "
        "as structured output and becomes machine-checkable evidence."
    )
    risk = RiskLevel.REVERSIBLE
    permissions = ["subprocess"]
    input_schema = {
        "type": "object",
        "properties": {
            "code": {"type": "string"},
            "timeout": {"type": "integer", "default": 60},
        },
        "required": ["code"],
    }

    def summarize(self, args: Dict[str, Any]) -> str:
        first = (args.get("code") or "").strip().splitlines()[:1]
        return f"run python analysis ({len(args.get('code',''))} chars): {first[0] if first else ''}"

    def run(self, ctx: ToolContext, args: Dict[str, Any]) -> ToolResult:
        scripts = os.path.join(ctx.workspace, ".state", "scripts")
        os.makedirs(scripts, exist_ok=True)
        fd, path = tempfile.mkstemp(suffix=".py", dir=scripts, prefix=f"{ctx.run_id}_")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(args["code"])
        timeout = min(int(args.get("timeout", 60)), 300)
        res = _run_argv([sys.executable, path], ctx, timeout)
        structured = None
        for line in (res.data.get("stdout") or "").splitlines():
            if line.startswith("RESULT_JSON:"):
                try:
                    structured = json.loads(line[len("RESULT_JSON:") :].strip())
                except json.JSONDecodeError:
                    structured = None
        res.data["script"] = path
        if structured is not None:
            res.data["result"] = structured
            res.evidence.append(
                {
                    "source_ref": f"python.run:{os.path.basename(path)}",
                    "excerpt": json.dumps(structured, sort_keys=True)[:400],
                }
            )
        return res


TOOLS = [ShellExec(), PythonAnalysis()]

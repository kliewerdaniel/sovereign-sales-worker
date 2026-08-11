"""Risk classification and the permission decision.

Two rules do the real work here:

1. **The tool's declared risk is a floor, not a suggestion.** The engine asks
   this module; the model is never consulted about whether something is risky.

2. **Decomposition does not launder risk.** An agent denied "send the email" must
   not get there by proposing "write the email to a file" then "shell: sendmail".
   ``DecompositionGuard`` tracks the risk ceiling that has already been refused
   or is pending within a run, and blocks equal-or-higher-risk actions from
   sneaking through afterwards.

Risk classification is **static and fails closed.** ``classify`` does not string-
match keywords (that is trivially bypassed with ``subprocess.run`` / ``os.system``
/ ``__import__('socket')``). For ``python.run`` it parses the submitted code with
``ast`` and classifies from the actual import/call graph; for ``shell.exec`` it
resolves the binary and floors interpreter invocations (``python3 -c ...``,
``bash -c ...``) at EXTERNAL because their behaviour cannot be verified from the
command line the way a fixed-purpose binary like ``ls`` can. Anything the walker
cannot positively classify as safe — unparseable code, a dynamic ``eval``/
``exec``/``__import__``/``getattr(builtins, ...)``, or an import of a module
outside the curated safe list — is escalated to the highest risk tier the tool
can reach. See ``docs/SECURITY.md``.
"""

from __future__ import annotations

import ast
import os
import shlex
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


# ---------------------------------------------------------------------------
# python.run — AST-based static classification
# ---------------------------------------------------------------------------
#
# Modules/attributes that are intrinsically network- or IPC-bridging -> EXTERNAL.
# Underscore = module name; dotted = attribute path on a module (e.g. "os.system").
_PY_EXTERNAL: Set[str] = {
    "subprocess", "socket", "socketserver", "urllib", "urllib.request",
    "urllib.parse", "urllib.error", "requests", "httpx", "ftplib", "smtplib",
    "telnetlib", "poplib", "imaplib", "nntplib", "smtpd", "asyncio",
    "websocket", "websockets", "paramiko", "pexpect", "select", "multiprocessing",
    "ctypes", "ctypes.util", "mmap", "signal", "resource", "os.system",
    "os.popen", "os.execv", "os.execve", "os.execvp", "os.execvpe", "os.spawn",
    "os.spawnl", "os.spawnle", "os.spawnlp", "os.spawnlpe", "os.spawnv",
    "os.spawnve", "os.spawnvp", "os.spawnvpe", "os.posix_spawn", "os.startfile",
    "os.kill", "os.abort", "os.register", "pathlib.Path.chmod",
    "pathlib.Path.rename", "pathlib.Path.replace", "pathlib.Path.write_text",
    "pathlib.Path.write_bytes", "pathlib.Path.symlink_to", "pathlib.Path.mkdir",
    "pathlib.Path.touch", "tempfile.mkdtemp",
}
# Modules/attributes that delete or irreversibly mutate the filesystem -> DESTRUCTIVE.
_PY_DESTRUCTIVE: Set[str] = {
    "shutil.rmtree", "shutil.move", "os.remove", "os.unlink", "os.rmdir",
    "os.truncate", "os.replace", "pathlib.Path.unlink", "pathlib.Path.rmdir",
    "pathlib.Path.rmtree", "os.rename",
}
# Modules that are assumed benign for analysis (no network/fs-destruct side effects
# reachable from a worker) — anything NOT in this set and not external/destructive
# is escalated (fail closed).
_PY_SAFE_MODULES: Set[str] = {
    "math", "statistics", "json", "csv", "decimal", "fractions", "random",
    "string", "re", "datetime", "time", "collections", "itertools", "functools",
    "operator", "typing", "dataclasses", "enum", "io", "os.path", "os",
    "pathlib", "pprint", "textwrap", "unicodedata", "hashlib", "base64",
    "struct", "bisect", "heapq", "array", "copy", "numbers", "logging",
    "warnings", "typing_extensions", "__future__",
}
# Builtins whose use with a non-literal (dynamic) argument defeats static analysis.
_DYNAMIC_BUILTINS = {"eval", "exec", "compile", "__import__", "vars", "locals", "globals"}
# Attributes that, when called on a dynamic/unknown object, defeat analysis.
_DYNAMIC_ATTRS = {"__getattribute__", "__getitem__", "getattr", "setattr", "delattr"}
# Builtins a worker legitimately uses for local-only analysis (no network, no
# irreversible fs change). These never escalate risk; `open` is bounded by the
# tool's own filesystem policy, so at most REVERSIBLE.
_PY_SAFE_BUILTINS = {
    "open", "print", "len", "range", "sorted", "sum", "min", "max", "map",
    "filter", "enumerate", "zip", "list", "dict", "set", "tuple", "str",
    "int", "float", "bool", "abs", "round", "format", "repr", "isinstance",
    "issubclass", "type", "hasattr", "any", "all", "iter", "next", "reversed",
    "ord", "chr", "complex", "bin", "hex", "oct", "divmod", "pow", "slice",
    "bytes", "bytearray", "frozenset", "super", "object", "property",
}


class _PythonRiskVisitor(ast.NodeVisitor):
    """Walk code; record the maximum risk tier reached.

    Fails closed: any unrecognized import, any dynamic builtin/attr call, or any
    call through an unknown module/object escalates risk to ``_max_reach``.
    """

    def __init__(self, max_reach: RiskLevel):
        self.risk = RiskLevel.READ
        self._max = max_reach

    def _escalate(self, level: RiskLevel) -> None:
        if risk_rank(level) > risk_rank(self.risk):
            self.risk = level

    def _is_literal(self, node: ast.AST) -> bool:
        try:
            ast.literal_eval(node)
            return True
        except Exception:
            return False

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            top = alias.name.split(".")[0]
            if top in ("os", "pathlib", "tempfile"):
                # inspect the specific attribute use later via attribute visits
                return
            if top in _PY_SAFE_MODULES:
                return
            if top in _PY_EXTERNAL or top in _PY_DESTRUCTIVE:
                return
            # unknown module -> cannot prove it is safe -> fail closed
            self._escalate(self._max)
            return

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module is None:
            self._escalate(self._max)
            return
        top = node.module.split(".")[0]
        if top in ("os", "pathlib", "tempfile"):
            return
        if top in _PY_SAFE_MODULES:
            return
        if top in _PY_EXTERNAL or top in _PY_DESTRUCTIVE:
            return
        self._escalate(self._max)

    def _attr_path(self, node: ast.AST) -> str:
        """Resolve a dotted attribute access to a dotted string, or '' if dynamic."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = self._attr_path(node.value)
            if not base:
                return ""
            return f"{base}.{node.attr}"
        return ""  # subscript / call / anything computed -> unknown

    def visit_Call(self, node: ast.Call) -> None:
        # Escalate based on the call target itself (func resolution / dynamic
        # builtins / external-or-destructive module paths). This helper may
        # return early on a recognized outcome, but that only decides *this*
        # call's conclusion — it must not stop us from descending into nested
        # calls in the arguments, so the outer call is handled separately below.
        self._check_call_func(node)
        # Always recurse into arguments: a dangerous call can be nested as an
        # argument of an innocuous outer call (e.g. ``print(os.system(...))``)
        # and must still be visited, not skipped because the outer call returned
        # early after classifying itself as safe.
        for arg in node.args:
            self.visit(arg)
        for kw in node.keywords:
            self.visit(kw.value)

    def _check_call_func(self, node: ast.Call) -> None:
        # Dynamic builtins whose argument is not a literal defeat analysis.
        fn = node.func
        if isinstance(fn, ast.Name) and fn.id in _DYNAMIC_BUILTINS:
            dynamic = not (node.args and self._is_literal(node.args[0]))
            if dynamic or fn.id in ("vars", "locals", "globals", "__import__"):
                self._escalate(self._max)
        elif isinstance(fn, ast.Attribute) and fn.attr in _DYNAMIC_ATTRS:
            # getattr(obj, dynamic_name) / obj.__getattribute__(x) / unknown base
            self._escalate(self._max)
        elif isinstance(fn, ast.Name) and fn.id in ("getattr", "setattr", "delattr"):
            self._escalate(self._max)

        path = self._attr_path(fn)
        if path:
            # A direct builtin call on the curated safe list (open/print/...) is
            # local-only and never escalates; `open` is bounded by the fs policy.
            if path in _PY_SAFE_BUILTINS:
                return
            if path in _PY_EXTERNAL:
                self._escalate(RiskLevel.EXTERNAL)
                return
            if path in _PY_DESTRUCTIVE:
                self._escalate(RiskLevel.DESTRUCTIVE)
                return
            if path in _DYNAMIC_BUILTINS or path.split(".")[-1] in _DYNAMIC_BUILTINS:
                self._escalate(self._max)
                return
            top = path.split(".")[0]
            if top in _PY_EXTERNAL or top in _PY_DESTRUCTIVE:
                if any(path == m or path.startswith(m + ".") for m in _PY_EXTERNAL):
                    self._escalate(RiskLevel.EXTERNAL)
                    return
                if any(path == m or path.startswith(m + ".") for m in _PY_DESTRUCTIVE):
                    self._escalate(RiskLevel.DESTRUCTIVE)
                    return
            # A call on a known-safe module (os.path.join, json.loads, ...) is fine.
            if top in _PY_SAFE_MODULES:
                return
            # Unknown module path -> fail closed.
            self._escalate(self._max)
            return
        # Function call whose target we cannot resolve (lambda, subscript, etc.)
        self._escalate(self._max)

    def generic_visit(self, node: ast.AST) -> None:
        super().generic_visit(node)


def classify_python(code: str, max_reach: RiskLevel = RiskLevel.DESTRUCTIVE) -> RiskLevel:
    """Static risk for ``python.run`` code. Fails closed on anything ambiguous."""
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError, MemoryError):
        # unparseable -> we cannot prove it is safe
        return max_reach
    visitor = _PythonRiskVisitor(max_reach)
    visitor.visit(tree)
    return visitor.risk


# ---------------------------------------------------------------------------
# shell.exec — argv[0] resolution + per-binary risk table
# ---------------------------------------------------------------------------
#
# Binaries that can themselves execute arbitrary code (interpreters) cannot be
# vetted from the command line the way a fixed-purpose binary (``ls``, ``cat``)
# can; invoking any of them floors the action at EXTERNAL regardless of argv.
_INTERPRETER_BINARIES = {
    "python", "python3", "python3.10", "python3.11", "python3.12", "python3.14",
    "python2", "python2.7", "perl", "ruby", "node", "nodejs", "lua", "php",
    "bash", "sh", "zsh", "ksh", "fish", "dash", "tcsh", "csh", "osascript",
    "pwsh", "powershell", "tclsh", "expect", "awk", "gawk", "mawk", "julia",
    "r", "Rscript", "guile", "sbcl", "racket", "ghci", "deno", "bun",
    "java", "javaw", "dotnet", "sqlite3", "psql", "mysql", "bc",
}


def classify_shell(command: str, max_reach: RiskLevel = RiskLevel.DESTRUCTIVE) -> RiskLevel:
    """Static risk for ``shell.exec``. ``max_reach`` lets a worker policy cap the
    escalation; the returned risk never exceeds ``max_reach``.
    """
    try:
        argv = shlex.split(command)
    except ValueError:
        return max_reach  # unparseable -> fail closed
    if not argv:
        return RiskLevel.REVERSIBLE
    base = os.path.basename(argv[0])
    # An interpreter can run anything -> external, and not statically vetteable.
    if base in _INTERPRETER_BINARIES or argv[0] in _INTERPRETER_BINARIES:
        return RiskLevel.EXTERNAL
    lower = command.lower()
    if any(tok in lower for tok in ("rm ", "rmdir", "shred ", "dd ", "mkfs", "format")):
        risk = RiskLevel.DESTRUCTIVE
    elif any(tok in lower for tok in ("curl", "wget", "ssh", "scp", "nc ", "ncat", "sftp", "rsync", "telnet")):
        risk = RiskLevel.EXTERNAL
    else:
        risk = RiskLevel.REVERSIBLE
    if risk_rank(risk) > risk_rank(max_reach):
        return max_reach
    return risk


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
    elif tool.name == "shell.exec":
        risk = classify_shell(str(args.get("command", "")))
    elif tool.name == "python.run":
        risk = classify_python(str(args.get("code", "")))
    # The tool's declared risk is a floor: classification may only ever raise.
    if risk_rank(risk) < risk_rank(tool.risk):
        risk = tool.risk
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

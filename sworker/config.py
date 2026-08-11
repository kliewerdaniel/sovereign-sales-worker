"""Worker identity + workspace configuration.

A Worker is a YAML file. That is deliberate: the thing that decides what an
autonomous agent is allowed to do should be a diffable, reviewable artifact in
version control, not rows a model can edit.

YAML is parsed by a tiny built-in reader (``_mini_yaml``) so the core has ZERO
third-party dependencies; if PyYAML is installed it is used instead.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .models import RiskLevel

DEFAULT_POLICY: Dict[str, str] = {
    "read": "auto",
    "reversible": "auto",
    "external": "approve",
    "financial": "approve",
    "destructive": "approve",
}

POLICY_VALUES = ("auto", "approve", "deny")


@dataclass
class WorkerConfig:
    name: str
    role: str = ""
    instructions: str = ""
    knowledge: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    procedures: List[str] = field(default_factory=list)
    policy: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_POLICY))
    workspace: str = ""
    fs_roots: List[str] = field(default_factory=list)     # writable/readable boundary
    shell_allow: List[str] = field(default_factory=list)  # allowlisted argv[0]
    env_allow: List[str] = field(default_factory=list)    # env vars passed to subprocesses
    max_steps: int = 12
    timeout: int = 60
    max_output: int = 20000
    path: str = ""

    def policy_for(self, risk: RiskLevel | str) -> str:
        return self.policy.get(RiskLevel(risk).value, "approve")

    def resolved_fs_roots(self) -> List[str]:
        """Absolute, realpath'd boundary roots. Always includes the workspace so
        artifacts and state are writable; never widens beyond declared roots."""
        roots = [os.path.realpath(r) for r in (self.fs_roots or [self.workspace])]
        ws = os.path.realpath(self.workspace)
        if ws not in roots:
            roots.append(ws)
        return roots

    def artifacts_dir(self) -> str:
        d = os.path.join(self.workspace, "artifacts", self.name)
        os.makedirs(d, exist_ok=True)
        return d

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "instructions": self.instructions,
            "knowledge": self.knowledge,
            "tools": self.tools,
            "procedures": self.procedures,
            "policy": self.policy,
            "workspace": self.workspace,
            "fs_roots": self.fs_roots,
            "shell_allow": self.shell_allow,
            "env_allow": self.env_allow,
            "max_steps": self.max_steps,
            "path": self.path,
        }


# ---------------------------------------------------------------------------
# workspace
# ---------------------------------------------------------------------------


@dataclass
class Workspace:
    """Everything the platform touches lives under one directory."""

    root: str

    @property
    def workers_dir(self) -> str:
        return os.path.join(self.root, "workers")

    @property
    def state_dir(self) -> str:
        return os.path.join(self.root, ".state")

    @property
    def artifacts_dir(self) -> str:
        return os.path.join(self.root, "artifacts")

    @property
    def procedures_dir(self) -> str:
        return os.path.join(self.root, "procedures")

    @property
    def atlas_dir(self) -> str:
        return os.path.join(self.state_dir, "atlas")

    @property
    def company_dir(self) -> str:
        return os.path.join(self.root, "company")

    def ensure(self) -> "Workspace":
        for d in (
            self.workers_dir,
            self.state_dir,
            self.artifacts_dir,
            self.procedures_dir,
            self.atlas_dir,
            self.company_dir,
        ):
            os.makedirs(d, exist_ok=True)
        return self


def default_workspace() -> Workspace:
    root = os.environ.get("SWORKER_HOME") or os.path.join(os.getcwd(), ".sworker")
    return Workspace(os.path.abspath(root))


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------


def load_worker(path: str, workspace: Optional[Workspace] = None) -> WorkerConfig:
    with open(path, "r", encoding="utf-8") as fh:
        data = parse_yaml(fh.read())
    if not isinstance(data, dict):
        raise ValueError(f"{path}: worker file must be a mapping")
    ws = workspace or default_workspace()
    policy = dict(DEFAULT_POLICY)
    for k, v in (data.get("policy") or {}).items():
        key = str(k).strip().lower()
        val = str(v).strip().lower()
        if key not in DEFAULT_POLICY:
            raise ValueError(f"{path}: unknown risk level in policy: {key!r}")
        if val not in POLICY_VALUES:
            raise ValueError(f"{path}: policy {key!r} must be one of {POLICY_VALUES}, got {val!r}")
        policy[key] = val
    base = os.path.dirname(os.path.abspath(path))

    def _abs(p: str) -> str:
        return p if os.path.isabs(p) else os.path.abspath(os.path.join(ws.root, p))

    cfg = WorkerConfig(
        name=str(data.get("name") or os.path.splitext(os.path.basename(path))[0]),
        role=str(data.get("role") or ""),
        instructions=str(data.get("instructions") or ""),
        knowledge=[_abs(str(k)) for k in (data.get("knowledge") or [])],
        tools=[str(t) for t in (data.get("tools") or [])],
        procedures=[str(p) for p in (data.get("procedures") or [])],
        policy=policy,
        workspace=ws.root,
        fs_roots=[_abs(str(r)) for r in (data.get("fs_roots") or [])] or [ws.root],
        shell_allow=[str(c) for c in (data.get("shell_allow") or [])],
        env_allow=[str(e) for e in (data.get("env_allow") or [])],
        max_steps=int(data.get("max_steps") or 12),
        path=os.path.abspath(path),
    )
    del base
    return cfg


def list_workers(workspace: Optional[Workspace] = None) -> List[WorkerConfig]:
    ws = workspace or default_workspace()
    if not os.path.isdir(ws.workers_dir):
        return []
    out = []
    for name in sorted(os.listdir(ws.workers_dir)):
        if name.endswith((".yaml", ".yml")):
            out.append(load_worker(os.path.join(ws.workers_dir, name), ws))
    return out


def get_worker(name: str, workspace: Optional[Workspace] = None) -> WorkerConfig:
    ws = workspace or default_workspace()
    for ext in (".yaml", ".yml"):
        p = os.path.join(ws.workers_dir, name + ext)
        if os.path.exists(p):
            return load_worker(p, ws)
    known = [w.name for w in list_workers(ws)]
    raise FileNotFoundError(f"no worker named {name!r} in {ws.workers_dir} (have: {known})")


# ---------------------------------------------------------------------------
# yaml
# ---------------------------------------------------------------------------


def parse_yaml(text: str) -> Any:
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except ImportError:
        return _mini_yaml(text)


def _mini_yaml(text: str) -> Any:
    """Minimal YAML subset: nested maps, '- ' lists, scalars, | block scalars.

    Enough for worker + procedure files. Raises on anything it does not
    understand rather than silently mis-parsing a permission policy.
    """
    lines = text.splitlines()
    pos = 0

    def scalar(tok: str) -> Any:
        tok = tok.strip()
        if not tok:
            return ""
        if tok[0] in "\"'" and tok[-1] == tok[0] and len(tok) > 1:
            return tok[1:-1]
        low = tok.lower()
        if low in ("true", "yes"):
            return True
        if low in ("false", "no"):
            return False
        if low in ("null", "~"):
            return None
        try:
            return int(tok)
        except ValueError:
            pass
        try:
            return float(tok)
        except ValueError:
            pass
        return tok

    def indent_of(ln: str) -> int:
        return len(ln) - len(ln.lstrip(" "))

    def block(min_indent: int) -> Any:
        nonlocal pos
        result: Any = None
        while pos < len(lines):
            raw = lines[pos]
            if not raw.strip() or raw.lstrip().startswith("#"):
                pos += 1
                continue
            ind = indent_of(raw)
            if ind < min_indent:
                break
            body = raw.strip()
            if body.startswith("- "):
                if result is None:
                    result = []
                if not isinstance(result, list):
                    break
                item = body[2:].strip()
                pos += 1
                if ":" in item and not item.startswith(("\"", "'")):
                    k, _, v = item.partition(":")
                    sub = {k.strip(): scalar(v)} if v.strip() else {}
                    if not v.strip():
                        sub[k.strip()] = block(ind + 2)
                    nxt = block(ind + 2)
                    if isinstance(nxt, dict):
                        sub.update(nxt)
                    result.append(sub)
                else:
                    result.append(scalar(item))
                continue
            if ":" not in body:
                raise ValueError(f"cannot parse YAML line: {raw!r}")
            key, _, rest = body.partition(":")
            key = key.strip()
            rest = rest.strip()
            if result is None:
                result = {}
            if not isinstance(result, dict):
                break
            pos += 1
            if rest in ("|", ">"):
                buf = []
                while pos < len(lines) and (not lines[pos].strip() or indent_of(lines[pos]) > ind):
                    buf.append(lines[pos][ind + 2 :] if lines[pos].strip() else "")
                    pos += 1
                joined = "\n".join(buf).rstrip()
                result[key] = joined if rest == "|" else " ".join(joined.split())
            elif rest.startswith("[") and rest.endswith("]"):
                inner = rest[1:-1].strip()
                result[key] = [scalar(x) for x in inner.split(",")] if inner else []
            elif rest:
                result[key] = scalar(rest)
            else:
                result[key] = block(ind + 1)
        return result

    parsed = block(0)
    return {} if parsed is None else parsed

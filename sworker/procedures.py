"""Procedural memory.

A Procedure is a YAML file: named, versioned, diffable, reviewable. It is NOT a
saved transcript — it is a structured program of steps with typed inputs and
deterministic verification checks attached.

``learn_from_run`` is the "learn how I do this" path: it reads a completed run's
ACTUAL executed actions from the ledger and generalises the literal values that
came from the task inputs back into ``{{placeholders}}``. It never invents a
step that was not really executed.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

from .config import WorkerConfig, Workspace, default_workspace, parse_yaml
from .store import WorkerStore


def procedures_dir(worker: WorkerConfig) -> str:
    d = os.path.join(worker.workspace, "procedures")
    os.makedirs(d, exist_ok=True)
    return d


def list_procedures(worker: WorkerConfig) -> List[Dict[str, Any]]:
    out = []
    d = procedures_dir(worker)
    for name in sorted(os.listdir(d)):
        if not name.endswith((".yaml", ".yml")):
            continue
        proc = load_procedure(worker, os.path.splitext(name)[0])
        if proc:
            out.append(proc)
    return out


def load_procedure(worker: WorkerConfig, name: str) -> Optional[Dict[str, Any]]:
    base = procedures_dir(worker)
    for cand in (name, f"{name}.yaml", f"{name}.yml"):
        p = cand if os.path.isabs(cand) else os.path.join(base, cand)
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as fh:
                data = parse_yaml(fh.read())
            if isinstance(data, dict):
                data.setdefault("name", os.path.splitext(os.path.basename(p))[0])
                data["path"] = p
                return data
    return None


def save_procedure(worker: WorkerConfig, name: str, body: str) -> str:
    path = os.path.join(procedures_dir(worker), f"{name}.yaml")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return path


# ---------------------------------------------------------------------------
# expansion
# ---------------------------------------------------------------------------

_PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")


def substitute(value: Any, inputs: Dict[str, Any]) -> Any:
    """Replace {{name}} placeholders. A whole-string placeholder keeps the
    input's native type (so {{limit}} stays an int)."""
    if isinstance(value, str):
        m = _PLACEHOLDER.fullmatch(value.strip())
        if m:
            return inputs.get(m.group(1), value)
        return _PLACEHOLDER.sub(lambda mm: str(inputs.get(mm.group(1), mm.group(0))), value)
    if isinstance(value, dict):
        return {k: substitute(v, inputs) for k, v in value.items()}
    if isinstance(value, list):
        return [substitute(v, inputs) for v in value]
    return value


def procedure_steps(proc: Dict[str, Any], inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Expand a procedure into engine steps, applying declared input defaults."""
    merged: Dict[str, Any] = {}
    for spec in proc.get("inputs") or []:
        if isinstance(spec, dict):
            for key, meta in spec.items():
                if isinstance(meta, dict) and "default" in meta:
                    merged[key] = meta["default"]
                elif not isinstance(meta, dict):
                    merged[key] = meta
        elif isinstance(spec, str):
            merged.setdefault(spec, "")
    merged.update(inputs or {})

    steps: List[Dict[str, Any]] = []
    for raw in proc.get("steps") or []:
        if isinstance(raw, str):
            steps.append({"description": raw, "tool": "", "args": {}})
            continue
        if not isinstance(raw, dict):
            continue
        step = substitute(dict(raw), merged)
        steps.append(
            {
                "description": str(step.get("description") or step.get("name") or step.get("tool") or ""),
                "tool": str(step.get("tool") or ""),
                "args": step.get("args") or {},
            }
        )
    return steps


def procedure_verifications(proc: Dict[str, Any], inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for v in proc.get("verification") or proc.get("verifications") or []:
        if isinstance(v, dict):
            out.append(substitute(dict(v), inputs or {}))
    return out


# ---------------------------------------------------------------------------
# learning
# ---------------------------------------------------------------------------


def learn_from_run(
    store: WorkerStore, run_id: str, name: str, *, inputs: Optional[Dict[str, Any]] = None
) -> str:
    """Turn a real, completed run into a reusable procedure.

    Only actions that ACTUALLY EXECUTED are included. Literal values matching a
    task input are generalised back into placeholders so the procedure is
    reusable rather than a one-off replay.
    """
    run = store.get("runs", run_id)
    if not run:
        raise KeyError(f"no run {run_id!r}")
    task = store.get("tasks", run["task_id"]) or {}
    known_inputs: Dict[str, Any] = dict(task.get("inputs") or {})
    known_inputs.update(inputs or {})
    reverse = {str(v): k for k, v in known_inputs.items() if str(v)}

    def generalise(value: Any) -> Any:
        if isinstance(value, str):
            if value in reverse:
                return "{{%s}}" % reverse[value]
            for lit, key in reverse.items():
                if lit and lit in value:
                    value = value.replace(lit, "{{%s}}" % key)
            return value
        if isinstance(value, dict):
            return {k: generalise(v) for k, v in value.items()}
        if isinstance(value, list):
            return [generalise(v) for v in value]
        return value

    actions = [
        a
        for a in store.find("actions", run_id=run_id, order="created")
        if a["status"] == "EXECUTED"
    ]
    if not actions:
        raise ValueError(
            f"run {run_id} executed no actions; there is no procedure to learn "
            "(refusing to write a procedure that was never demonstrated)"
        )

    lines = [
        f"name: {name}",
        f"intent: {task.get('request', '').strip() or name}",
        f"learned_from_run: {run_id}",
        "trigger:",
        "  type: manual",
    ]
    if known_inputs:
        lines.append("inputs:")
        for k, v in known_inputs.items():
            lines.append(f"  - {k}:")
            lines.append(f"      default: {v!r}")
    lines.append("steps:")
    for a in actions:
        step = store.get("steps", a["step_id"]) or {}
        desc = generalise(step.get("description") or a["tool"])
        lines.append(f"  - description: {desc!r}")
        lines.append(f"    tool: {a['tool']}")
        args = generalise(a.get("args") or {})
        if args:
            lines.append("    args:")
            for k, v in args.items():
                lines.append(f"      {k}: {_yaml_scalar(v)}")

    vers = store.find("verifications", run_id=run_id)
    if vers:
        lines.append("verification:")
        for v in vers:
            lines.append(f"  - check: {v['check']}")

    return "\n".join(lines) + "\n"


def _yaml_scalar(v: Any) -> str:
    import json as _json

    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, (dict, list)):
        return _json.dumps(v)
    return _json.dumps(str(v))

#!/usr/bin/env python3
"""sworker — the Sovereign AI Worker Platform command line.

Local-first. No cloud. Every action is recorded and reconstructable.

    python -m sworker <command> [args]

Commands:
    init                scaffold a workspace (.sworker/) with an example worker
    workers             list configured workers
    show <worker>       print a worker's identity + policy
    run <worker> "req"  execute a request end-to-end (auto-approve by policy)
    approve <appr_id>   approve a pending approval (or: deny)
    deny <appr_id>      reject a pending approval
    resume <run_id>     continue a run awaiting approval after a decision
    runs [worker]       list runs
    run <id>            show one run's events + evidence + artifacts (id is numeric-ish)
    verify <run>        run any declared verification checks for a run
    learn <run> <name>  capture a completed run as a reusable procedure
    proc [worker]       list procedures
    sched add <w> <p> <cron>   schedule a procedure on a worker
    sched [worker]      list schedules
    sched off <id>      disable a schedule
    audit <run_id>      replay the raw append-only event log for a run

Examples:
    python -m sworker init
    python -m sworker run analyst "What were total Q2 sales?"
    python -m sworker approve appr_3Kf
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List

from . import __version__
from .config import WorkerConfig, default_workspace, get_worker, list_workers, load_worker
from .store import WorkerStore
from .inference import Inference, NullInference
from .engine import WorkerEngine
from .approvals import ApprovalManager
from .procedures import learn_from_run, list_procedures, load_procedure, save_procedure
from . import scheduler as sched_mod
from . import web as web_mod


def _store() -> WorkerStore:
    ws = default_workspace()
    return WorkerStore(ws.state_dir)


def _engine(worker: WorkerConfig) -> WorkerEngine:
    try:
        llm = Inference.from_env()
    except RuntimeError:
        llm = NullInference()
        print("[inference] no local model at SWORKER_LLM_URL; using deterministic fallback", file=sys.stderr)
    return WorkerEngine(worker, _store(), inference=llm)


def _fmt_run(rec: Dict[str, Any]) -> str:
    return (
        f"  #{rec['seq']:>3}  {rec['id']}  {rec['status']:<20} "
        f"ev={rec.get('evidence_count',0)} art={rec.get('artifact_count',0) or len(rec.get('artifact_ids',[]))}  {rec.get('summary','')[:60]}"
    )


def cmd_init(args) -> int:
    ws = default_workspace()
    ws.ensure()
    wf = os.path.join(ws.workers_dir, "analyst.yaml")
    if not os.path.exists(wf):
        open(wf, "w").write(
            "name: analyst\n"
            "role: local business analyst\n"
            "instructions: |\n"
            "  Read company data under company/, answer questions with computed evidence,\n"
            "  and write reports to artifacts/ when asked.\n"
            "tools: [fs.list, fs.read, fs.write, data.query, data.inspect, knowledge.search]\n"
            "policy:\n"
            "  read: auto\n"
            "  reversible: auto\n"
            "  external: approve\n"
            "  financial: approve\n"
            "  destructive: approve\n"
        )
    os.makedirs(os.path.join(ws.root, "company"), exist_ok=True)
    open(os.path.join(ws.root, "company", "example.csv"), "w").write(
        "region,quarter,revenue\nnorth,Q1,120\nnorth,Q2,150\nsouth,Q1,90\nsouth,Q2,140\n"
    )
    print(f"workspace initialised at {ws.root}")
    print(f"  worker 'analyst' created. Data goes in {os.path.join(ws.root,'company')}")
    print("  try: python -m sworker run analyst \"What were total Q2 revenue?\"")
    return 0


def cmd_workers(args) -> int:
    for w in list_workers():
        print(f"{w.name:<16} {w.role:<28} tools={len(w.tools)} policy={w.policy}")
    return 0


def cmd_show(args) -> int:
    w = get_worker(args.worker)
    print(f"name: {w.name}")
    print(f"role: {w.role}")
    print(f"tools: {', '.join(w.tools) or '(all)'}")
    print("policy:")
    for k, v in w.policy.items():
        print(f"  {k:<12} {v}")
    print(f"workspace: {w.workspace}")
    return 0


def cmd_run(args) -> int:
    worker = get_worker(args.worker)
    eng = _engine(worker)
    store = eng.store
    res = eng.run(args.request, inputs=_inputs(args), on_event=_printer)
    print()
    print("=" * 64)
    print(f"RUN #{res.run.seq}  {res.status.value}")
    print("-" * 64)
    print(res.summary)
    for art in res.artifacts:
        print(f"  artifact: {art.path}")
    if res.pending_approvals:
        print("  PENDING APPROVALS:")
        for a in res.pending_approvals:
            print(f"    {a['id']}  {a['summary']}  [{a['risk']}]")
        print(f"  -> review with: python -m sworker show-approval <id>")
    print(f"  replay audit: python -m sworker audit {res.run.id}")
    return 0 if res.ok else 1


def _printer(event: str, payload: Dict[str, Any]) -> None:
    if event in ("run.started", "run.finished", "plan.created"):
        return
    if event == "step.done":
        print(f"  ✓ {payload.get('step','')[:60]}  ({payload.get('tool')})")
    elif event == "step.failed":
        print(f"  ✗ {payload.get('step','')[:60]}  ERROR: {payload.get('error','')[:80]}")
    elif event == "step.blocked":
        print(f"  ⊘ blocked: {payload.get('step','')[:60]}  ({payload.get('reason','')[:60]})")
    elif event == "approval.requested":
        print(f"  ⏳ approval requested: {payload.get('id')} [{payload.get('risk')}] {payload.get('summary')}")


def _inputs(args) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for kv in args.input or []:
        if "=" in kv:
            k, _, v = kv.partition("=")
            out[k] = v
    return out


def cmd_approve(args) -> int:
    return _decide(args.appr_id, True, args.note)


def cmd_deny(args) -> int:
    return _decide(args.appr_id, False, args.note)


def _decide(appr_id: str, approved: bool, note: str) -> int:
    store = _store()
    mgr = ApprovalManager(store)
    try:
        rec = mgr.decide(appr_id, approved=approved, by="cli", note=note or "")
    except KeyError as exc:
        print(f"no pending approval {appr_id!r}", file=sys.stderr)
        return 1
    verb = "APPROVED" if approved else "REJECTED"
    print(f"{verb} {appr_id} ({rec['summary']})")
    print(f"  resume the run with: python -m sworker resume {rec['run_id']}")
    return 0


def cmd_resume(args) -> int:
    store = _store()
    run = store.get("runs", args.run_id)
    if not run:
        print(f"no run {args.run_id!r}", file=sys.stderr)
        return 1
    worker = get_worker(run["worker"])
    eng = _engine(worker)
    # reuse engine but only for resume
    res = eng.run("", resume_run_id=args.run_id, on_event=_printer)
    print()
    print(f"RUN {args.run_id}  -> {res.status.value}")
    print(res.summary)
    return 0 if res.ok else 1


def cmd_runs(args) -> int:
    store = _store()
    rows = store.find("runs", order="seq", desc=True)
    if args.worker:
        rows = [r for r in rows if r["worker"] == args.worker]
    if not rows:
        print("(no runs)")
        return 0
    for r in rows[: args.limit]:
        print(_fmt_run(r))
    return 0


def cmd_run_show(args) -> int:
    store = _store()
    run = store.get("runs", args.run_id)
    if not run:
        # allow lookup by seq
        for r in store.find("runs", order="seq"):
            if str(r["seq"]) == args.run_id:
                run = r
                break
    if not run:
        print(f"no run {args.run_id!r}", file=sys.stderr)
        return 1
    print(f"RUN #{run['seq']}  {run['id']}")
    print(f"worker: {run['worker']}  status: {run['status']}")
    print(f"intent: {run.get('intent','')}")
    print(f"summary: {run['summary']}")
    print("\nsteps:")
    for s in store.find("steps", run_id=run["id"], order="idx"):
        print(f"  [{s['status']:<18}] {s.get('description','')[:60]}")
    print("\nevidence:")
    for e in store.find("evidence", run_id=run["id"], order="created"):
        print(f"  ({e['provenance']}) {e['summary'][:80]}")
    print("\nartifacts:")
    for a in store.find("artifacts", run_id=run["id"], order="created"):
        print(f"  {a['path']}  ({a.get('bytes',0)} bytes)")
    pending = ApprovalManager(store).pending(run["id"])
    if pending:
        print("\npending approvals:")
        for a in pending:
            print(f"  {a['id']}  {a['summary']}  [{a['risk']}]")
    return 0


def cmd_audit(args) -> int:
    store = _store()
    for rec in store.iter_audit(args.run_id):
        if args.run_id and rec.get("payload", {}).get("run_id") != args.run_id and rec.get("id") != args.run_id:
            continue
        print(f"{rec['ts']:.3f}  {rec['event']:<22} {rec['table']:<13} {rec['id']}")
    return 0


def cmd_learn(args) -> int:
    store = _store()
    body = learn_from_run(store, args.run_id, args.name)
    worker = None
    # best-effort: find the worker that owns the run
    run = store.get("runs", args.run_id)
    if run:
        try:
            worker = get_worker(run["worker"])
        except Exception:
            worker = None
    if worker:
        path = save_procedure(worker, args.name, body)
    else:
        path = os.path.join(default_workspace().procedures_dir, f"{args.name}.yaml")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").write(body)
    print(f"procedure saved: {path}")
    return 0


def cmd_proc(args) -> int:
    store = _store()
    if args.worker:
        worker = get_worker(args.worker)
        procs = list_procedures(worker)
    else:
        procs = []
        for w in list_workers():
            procs.extend(list_procedures(w))
    if not procs:
        print("(no procedures)")
        return 0
    for p in procs:
        print(f"  {p.get('name'):<20} learned_from={p.get('learned_from_run','-')}  {p.get('intent','')[:50]}")
    return 0


def cmd_sched(args) -> int:
    store = _store()
    if args.sub == "add":
        sched_mod.add_schedule(store, args.worker, args.procedure, args.cron)
        print(f"scheduled {args.procedure} on {args.worker} at '{args.cron}'")
        return 0
    if args.sub == "off":
        sched_mod.set_enabled(store, args.id, False)
        print(f"disabled schedule {args.id}")
        return 0
    # list
    rows = sched_mod.list_schedules(store, args.worker)
    if not rows:
        print("(no schedules)")
        return 0
    now_s = time.time()
    for s in rows:
        due = "DUE" if (s["enabled"] and s["next_run"] and s["next_run"] <= now_s) else ""
        nxt = time.strftime("%Y-%m-%d %H:%M", time.localtime(s["next_run"])) if s.get("next_run") else "-"
        print(f"  {s['id']}  {s['worker']}/{s['procedure']}  {s['cron']:<14} next={nxt} {due} {'[off]' if not s['enabled'] else ''}")
    return 0


def cmd_verify(args) -> int:
    store = _store()
    run = store.get("runs", args.run_id)
    if not run:
        print(f"no run {args.run_id!r}", file=sys.stderr)
        return 1
    worker = get_worker(run["worker"])
    eng = _engine(worker)
    from .procedures import load_procedure, procedure_verifications

    proc = None
    if run.get("procedure"):
        proc = load_procedure(worker, run["procedure"])
    specs = (proc and procedure_verifications(proc, {})) or run.get("verifications") or []
    if not specs:
        print("no verification checks declared for this run")
        return 0
    print(f"verifying run {args.run_id} ({len(specs)} checks):")
    any_fail = False
    for spec in specs:
        v = eng.record_verification(run, spec, eng._tool_ctx(run))
        flag = "PASS" if v.outcome.value == "PASS" else ("FAIL" if v.outcome.value == "FAIL" else "UNVERIFIABLE")
        if flag == "FAIL":
            any_fail = True
        print(f"  [{flag}] {v.check}: {v.detail}")
    return 1 if any_fail else 0


def cmd_web(args) -> int:
    web_mod.serve(port=args.port, home=args.home)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sworker", description="Sovereign AI Worker Platform (local-first)")
    p.add_argument("--version", action="version", version=f"sworker {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="scaffold a workspace").set_defaults(func=cmd_init)

    sub.add_parser("workers", help="list workers").set_defaults(func=cmd_workers)
    s = sub.add_parser("show", help="show worker identity")
    s.add_argument("worker"); s.set_defaults(func=cmd_show)

    r = sub.add_parser("run", help="run a request")
    r.add_argument("worker"); r.add_argument("request")
    r.add_argument("-i", "--input", action="append", help="key=value run inputs")
    r.set_defaults(func=cmd_run)

    a = sub.add_parser("approve", help="approve a pending approval")
    a.add_argument("appr_id"); a.add_argument("--note", default=""); a.set_defaults(func=cmd_approve)
    d = sub.add_parser("deny", help="deny a pending approval")
    d.add_argument("appr_id"); d.add_argument("--note", default=""); d.set_defaults(func=cmd_deny)

    rs = sub.add_parser("resume", help="resume a run after approval")
    rs.add_argument("run_id"); rs.set_defaults(func=cmd_resume)

    rn = sub.add_parser("runs", help="list runs")
    rn.add_argument("worker", nargs="?"); rn.add_argument("-n", "--limit", type=int, default=20); rn.set_defaults(func=cmd_runs)
    rsh = sub.add_parser("run-info", help="show one run"); rsh.add_argument("run_id"); rsh.set_defaults(func=cmd_run_show)

    au = sub.add_parser("audit", help="replay event log for a run")
    au.add_argument("run_id"); au.set_defaults(func=cmd_audit)

    l = sub.add_parser("learn", help="capture a run as a procedure")
    l.add_argument("run_id"); l.add_argument("name"); l.set_defaults(func=cmd_learn)

    pr = sub.add_parser("proc", help="list procedures"); pr.add_argument("worker", nargs="?"); pr.set_defaults(func=cmd_proc)

    sc = sub.add_parser("sched", help="manage schedules")
    scsub = sc.add_subparsers(dest="sub", required=True)
    scadd = scsub.add_parser("add"); scadd.add_argument("worker"); scadd.add_argument("procedure"); scadd.add_argument("cron"); scadd.set_defaults(func=cmd_sched)
    scoff = scsub.add_parser("off"); scoff.add_argument("id"); scoff.set_defaults(func=cmd_sched)
    scsub.add_parser("list").set_defaults(func=cmd_sched, sub="list")
    sc.set_defaults(sub="list")

    v = sub.add_parser("verify", help="run verification checks for a run")
    v.add_argument("run_id"); v.set_defaults(func=cmd_verify)

    w = sub.add_parser("web", help="launch the local web UI")
    w.add_argument("--port", type=int, default=8777)
    w.add_argument("--home", default="")
    w.set_defaults(func=cmd_web)

    return p


def main(argv: List[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

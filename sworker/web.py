"""Minimal local-first web UI.

A single-file HTTP server built on stdlib ``http.server`` so the core keeps ZERO
third-party dependencies. It serves one page that lists workers, runs, and lets
you:

  * submit a request to a worker (POST) and watch the run appear;
  * replay a run's audit trail + evidence + artifacts;
  * approve / reject a pending approval and then resume the run;
  * run a run's declared verification checks.

Everything reads from and writes to the same local store the CLI uses — there is
no separate database, nothing leaves the machine. The server binds to
``127.0.0.1`` only.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from .config import default_workspace, get_worker, list_workers
from .store import WorkerStore
from .engine import WorkerEngine
from .approvals import ApprovalManager
from .inference import NullInference
from .procedures import load_procedure, procedure_verifications


def _esc(s: str) -> str:
    return html.escape(str(s))


def _time(ts: float) -> str:
    if not ts:
        return "-"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def page(title: str, body: str) -> str:
    return (
        f"<!doctype html><html lang=en><head><meta charset=utf-8>"
        f"<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>{_esc(title)}</title>"
        f"<style>"
        f"body{{font:14px/1.5 system-ui,Segoe UI,Arial;margin:0;background:#0f1115;color:#e6e6e6}}"
        f"a{{color:#7cc4ff;text-decoration:none}}a:hover{{text-decoration:underline}}"
        f"header{{padding:14px 20px;background:#161a21;border-bottom:1px solid #23272f}}"
        f"h1{{margin:0;font-size:18px}}h2{{font-size:15px;color:#aab}}"
        f".wrap{{padding:20px;max-width:1000px;margin:0 auto}}"
        f"table{{width:100%;border-collapse:collapse;margin:8px 0}}"
        f"th,td{{text-align:left;padding:7px 9px;border-bottom:1px solid #23272f;vertical-align:top}}"
        f"th{{color:#8a93a3;font-weight:600;font-size:12px;text-transform:uppercase}}"
        f".pill{{display:inline-block;padding:1px 8px;border-radius:10px;font-size:11px;background:#23272f}}"
        f".ok{{background:#173a23;color:#7ee2a8}}.bad{{background:#3a1717;color:#ff9a9a}}"
        f".warn{{background:#3a3417;color:#ffe08a}}.mono{{font-family:ui-monospace,Menlo,monospace;font-size:12px}}"
        f".pend{{background:#2a2438;color:#c9a8ff}}code{{background:#1b1f27;padding:1px 5px;border-radius:4px}}"
        f"pre{{background:#161a21;border:1px solid #23272f;border-radius:8px;padding:12px;overflow:auto;max-height:420px}}"
        f".row{{display:flex;gap:12px;flex-wrap:wrap}}.card{{background:#161a21;border:1px solid #23272f;border-radius:8px;padding:12px;flex:1;min-width:220px}}"
        f"form{{display:flex;gap:8px;margin:10px 0}}input,select,textarea{{background:#0f1115;color:#e6e6e6;border:1px solid #2a2f38;padding:7px 9px;border-radius:6px}}"
        f"button{{background:#2563eb;color:#fff;border:0;padding:7px 14px;border-radius:6px;cursor:pointer}}"
        f".danger{{background:#a33}}.ghost{{background:transparent;border:1px solid #2a2f38}}"
        f"</style></head><body><header><h1>🛡 Sovereign AI Worker</h1></header>"
        f"<div class=wrap>{body}</div></body></html>"
    )


# ---------------------------------------------------------------------------
# engine helper (same store + deterministic fallback as the CLI)
# ---------------------------------------------------------------------------

def _engine_for(ws, worker_name: str) -> WorkerEngine:
    from .inference import Inference

    worker = get_worker(worker_name, ws)
    store = WorkerStore(ws.state_dir)
    try:
        llm = Inference.from_env()
    except RuntimeError:
        llm = NullInference()
    return WorkerEngine(worker, store, inference=llm)


def _status_pill(status: str) -> str:
    cls = (
        "ok" if status == "SUCCESS"
        else "bad" if status in ("FAILED", "BLOCKED")
        else "pend" if status in ("AWAITING_APPROVAL", "INSUFFICIENT_EVIDENCE")
        else "warn"
    )
    return f"<span class='pill {cls}'>{_esc(status)}</span>"


# ---------------------------------------------------------------------------
# views
# ---------------------------------------------------------------------------

def render_index(store: WorkerStore, ws) -> str:
    workers = list_workers(ws)
    runs = store.find("runs", order="seq", desc=True)[:25]
    wcards = "".join(
        f"<div class=card><b>{_esc(w.name)}</b><br><span style='color:#8a93a3'>{_esc(w.role)}</span><br>"
        f"tools: {_esc(', '.join(w.tools) or '(all)')}</div>"
        for w in workers
    ) or "<i>no workers — run <code>python -m sworker init</code></i>"
    rrows = "".join(
        f"<tr><td>#{r['seq']}</td><td><code>{_esc(r['id'])}</code></td><td>{_esc(r['worker'])}</td>"
        f"<td>{_status_pill(r['status'])}</td><td>{_esc(r.get('summary', '')[:90])}</td>"
        f"<td><a href='/run?run_id={_esc(r['id'])}'>view</a></td></tr>"
        for r in runs
    ) or "<tr><td colspan=6><i>no runs yet</i></td></tr>"
    opts = "".join(f"<option>{_esc(w.name)}</option>" for w in workers)
    form = (
        "<form action='/run' method=post>"
        "<select name=worker>" + opts + "</select>"
        "<input name=request placeholder='request...' size=50 required>"
        "<button>Run</button></form>"
    )
    return (
        f"<h2>Workers</h2><div class=row>{wcards}</div>"
        f"<h2>New run</h2>{form}"
        f"<h2>Runs</h2>"
        f"<table><tr><th>#</th><th>id</th><th>worker</th><th>status</th><th>summary</th><th></th></tr>{rrows}</table>"
        f"<p style='color:#8a93a3'>JSON API: <a href='/api/runs'>/api/runs</a></p>"
    )


def _render_approvals(store, run_id: str) -> str:
    mgr = ApprovalManager(store)
    pending = mgr.pending(run_id)
    if not pending:
        return ""
    rows = "".join(
        f"<tr><td><code>{_esc(a['id'])}</code></td><td>{_esc(a['summary'])}</td>"
        f"<td><span class='pill'>{_esc(a['risk'])}</span></td>"
        f"<td><form action='/approve' method=post style='margin:0'>{_hidden('appr_id', a['id'])}"
        f"<button type=submit>Approve</button></form></td>"
        f"<td><form action='/deny' method=post style='margin:0'>{_hidden('appr_id', a['id'])}"
        f"<button type=submit class=danger>Reject</button></form></td></tr>"
        for a in pending
    )
    return (
        f"<h2>Pending approvals</h2><table>"
        f"<tr><th>id</th><th>summary</th><th>risk</th><th></th><th></th></tr>{rows}</table>"
    )


def _hidden(name: str, val: str) -> str:
    return f"<input type=hidden name={name} value={_esc(val)}>"


def render_run(store: WorkerStore, ws, run_id: str) -> str:
    run = store.get("runs", run_id)
    if not run:
        return "<h2>Run not found</h2><a href='/'>back</a>"
    steps = store.find("steps", run_id=run_id, order="idx")
    evs = store.find("evidence", run_id=run_id, order="created")
    arts = store.find("artifacts", run_id=run_id, order="created")
    audit = [e for e in store.iter_audit(run_id)]
    srows = "".join(
        f"<tr><td><span class='pill'>{_esc(s['status'])}</span></td><td>{_esc(s.get('description', ''))}</td>"
        f"<td><code>{_esc(s.get('tool', ''))}</code></td></tr>"
        for s in steps
    )
    erows = "".join(
        f"<tr><td>{_esc(e['provenance'])}</td><td>{_esc(e['summary'])}</td>"
        f"<td class=mono>{_esc(e.get('source_ref', ''))}</td></tr>"
        for e in evs
    )
    arows = "".join(
        f"<tr><td><a href='/?dl={_esc(a['path'])}'>{_esc(a['path'])}</a></td><td>{a.get('bytes', 0)} b</td></tr>"
        for a in arts
    )
    audit_txt = "\n".join(f"{_time(e['ts'])}  {e['event']:<22} {e['table']:<13} {e['id']}" for e in audit)
    verify_btn = (
        f"<form action='/verify' method=post style='display:inline'>{_hidden('run_id', run_id)}"
        f"<button type=submit>Run verification</button></form>"
    )
    if run["status"] in ("AWAITING_APPROVAL",):
        resume_btn = (
            f"<form action='/resume' method=post style='display:inline'>{_hidden('run_id', run_id)}"
            f"<button type=submit>Resume run</button></form>"
        )
    else:
        resume_btn = ""
    return (
        f"<h2>Run #{run['seq']} {_status_pill(run['status'])}</h2>"
        f"<p>{_esc(run.get('summary', ''))}</p>"
        f"<p style='color:#8a93a3'>worker: <b>{_esc(run['worker'])}</b> · intent: {_esc(run.get('intent', ''))} · "
        f"evidence: {len(evs)} · artifacts: {len(arts)} · "
        f"replay: <code>python -m sworker audit {_esc(run_id)}</code></p>"
        f"<p>{verify_btn} {resume_btn}</p>"
        f"{_render_approvals(store, run_id)}"
        f"<h2>Steps</h2><table>{srows}</table>"
        f"<h2>Evidence</h2><table>{erows or '<tr><td><i>none</i></td></tr>'}</table>"
        f"<h2>Artifacts</h2><table>{arows or '<tr><td><i>none</i></td></tr>'}</table>"
        f"<h2>Audit trail ({len(audit)} events)</h2><pre class=mono>{_esc(audit_txt)}</pre>"
        f"<p><a href='/'>← back</a></p>"
    )


def render_verify(store: WorkerStore, ws, run_id: str) -> str:
    run = store.get("runs", run_id)
    if not run:
        return "<h2>Run not found</h2><a href='/'>back</a>"
    worker = get_worker(run["worker"], ws)
    eng = _engine_for(ws, run["worker"])
    proc = load_procedure(worker, run["procedure"]) if run.get("procedure") else None
    specs = (proc and procedure_verifications(proc, {})) or run.get("verifications") or []
    if not specs:
        return (
            f"<h2>Verification</h2><p>no verification checks declared for run {_esc(run_id)}.</p>"
            f"<p><a href='/run?run_id={_esc(run_id)}'>← back to run</a></p>"
        )
    rows = []
    any_fail = False
    for raw_spec in specs:
        spec = raw_spec if isinstance(raw_spec, dict) else {}
        v = eng.record_verification(run, spec, eng._tool_ctx(run))
        flag = v.outcome.value
        if flag == "FAIL":
            any_fail = True
        cls = "ok" if flag == "PASS" else ("bad" if flag == "FAIL" else "warn")
        rows.append(
            f"<tr><td><span class='pill {cls}'>{_esc(flag)}</span></td>"
            f"<td><code>{_esc(v.check)}</code></td><td>{_esc(v.detail)}</td>"
            f"<td>{_esc(str(v.actual))}</td></tr>"
        )
    head = "FAILED" if any_fail else "ALL PASSED"
    return (
        f"<h2>Verification — {_esc(head)}</h2>"
        f"<table><tr><th>result</th><th>check</th><th>detail</th><th>actual</th></tr>{''.join(rows)}</table>"
        f"<p><a href='/run?run_id={_esc(run_id)}'>← back to run</a></p>"
    )


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def __init__(self, *a, store=None, ws=None, **k):
        self._store = store
        self._ws = ws
        super().__init__(*a, **k)

    def log_message(self, fmt, *args):  # type: ignore[override]
        pass

    def _send(self, body: "str | bytes", ctype="text/html; charset=utf-8", code=200):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _qs(self):
        return parse_qs(urlparse(self.path).query)

    def _form(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        data = parse_qs(raw.decode("utf-8", "replace"))
        return {k: (v[0] if v else "") for k, v in data.items()}

    def do_GET(self):
        url = urlparse(self.path)
        qs = self._qs()
        try:
            if url.path == "/run" and qs.get("run_id"):
                self._send(page("Run", render_run(self._store, self._ws, qs["run_id"][0])))
            elif url.path == "/verify" and qs.get("run_id"):
                self._send(page("Verify", render_verify(self._store, self._ws, qs["run_id"][0])))
            elif url.path == "/api/runs":
                self._send(
                    json.dumps(self._store.find("runs", order="seq", desc=True)[:50]).encode(),
                    "application/json",
                )
            else:
                self._send(page("Sovereign AI Worker", render_index(self._store, self._ws)))
        except Exception:  # pragma: no cover
            self._send(page("Error", f"<pre class=mono>{_esc(traceback.format_exc())}</pre>").encode(), code=500)

    def do_POST(self):
        url = urlparse(self.path)
        form = self._form()
        try:
            if url.path == "/run":
                worker = form.get("worker", "")
                request = form.get("request", "").strip()
                if not worker or not request:
                    self._send(page("Error", "<p>worker + request required</p>").encode(), code=400)
                    return
                eng = _engine_for(self._ws, worker)
                res = eng.run(request, on_event=lambda e, p: None)
                self._redirect(f"/run?run_id={res.run.id}")
            elif url.path == "/approve":
                self._decide(form.get("appr_id", ""), True)
            elif url.path == "/deny":
                self._decide(form.get("appr_id", ""), False)
            elif url.path == "/resume":
                run_id = form.get("run_id", "")
                run = self._store.get("runs", run_id)
                if not run:
                    self._send(page("Error", "<p>no such run</p>").encode(), code=404)
                    return
                eng = _engine_for(self._ws, run["worker"])
                res = eng.run("", resume_run_id=run_id, on_event=lambda e, p: None)
                self._redirect(f"/run?run_id={res.run.id}")
            elif url.path == "/verify":
                run_id = form.get("run_id", "")
                self._redirect(f"/verify?run_id={run_id}")
            else:
                self._send(page("Error", "<p>unknown action</p>").encode(), code=404)
        except Exception:  # pragma: no cover
            self._send(page("Error", f"<pre class=mono>{_esc(traceback.format_exc())}</pre>").encode(), code=500)

    def _decide(self, appr_id: str, approved: bool):
        if not appr_id:
            self._send(page("Error", "<p>missing approval id</p>").encode(), code=400)
            return
        mgr = ApprovalManager(self._store)
        try:
            rec = mgr.decide(appr_id, approved=approved, by="web", note="via web UI")
        except KeyError:
            self._send(page("Error", f"<p>no pending approval {appr_id!r}</p>").encode(), code=404)
            return
        self._redirect(f"/run?run_id={rec['run_id']}")

    def _redirect(self, loc: str):
        body = page("Redirecting", f"<p><a href='{_esc(loc)}'>continue</a></p>")
        self.send_response(303)
        self.send_header("Location", loc)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(port: int = 8777, home: str = ""):
    if home:
        os.environ["SWORKER_HOME"] = os.path.abspath(home)
    ws = default_workspace()
    ws.ensure()
    store = WorkerStore(ws.state_dir)
    httpd = ThreadingHTTPServer(
        ("127.0.0.1", port), lambda *a, **k: Handler(*a, store=store, ws=ws, **k)
    )
    print(f"Sovereign AI Worker UI on http://127.0.0.1:{port}  (Ctrl-C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


def cli(argv=None):
    ap = argparse.ArgumentParser(prog="sworker.web")
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--home", default="")
    args = ap.parse_args(argv)
    serve(port=args.port, home=args.home)


if __name__ == "__main__":
    cli()

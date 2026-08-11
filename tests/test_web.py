"""Integration tests for the local-first web UI (sworker.web).

Real HTTP against a live ThreadingHTTPServer, no mocks. Exercises the full
surface: index, submit-run, run page, approval -> resume loop, verify, and the
JSON API. Uses the same deterministic fallback engine as the CLI.

Run with:  env -u PYTHONPATH -u PYTHONHOME /opt/homebrew/bin/python3.14 -m pytest tests/
"""

from __future__ import annotations

import os
import socket
import threading
import urllib.parse
import urllib.request
from http.client import HTTPResponse
from urllib.error import HTTPError

import pytest

from sworker.config import Workspace
from sworker.store import WorkerStore
from sworker.approvals import ApprovalManager
from sworker import web as web_mod


SALES_CSV = """region,quarter,revenue,orders
North,Q1,42000,1320
North,Q2,51000,1480
South,Q1,31000,980
South,Q2,35500,1100
Online,Q1,88000,4200
Online,Q2,102000,5100
"""

WORKER_YAML = """name: acme-analyst
role: Acme Coffee business analyst
instructions: |
  Compute figures from the CSVs with data.query.
tools: [fs.list, fs.read, fs.write, data.query, data.inspect, knowledge.search]
policy:
  read: auto
  reversible: auto
  external: approve
  financial: approve
  destructive: approve
fs_roots: [company]
"""

# A worker whose reversible writes require approval -> exercises the gate.
GATED_WORKER_YAML = """name: acme-gated
role: Acme Coffee gated analyst
instructions: |
  Compute figures from the CSVs with data.query.
tools: [fs.list, fs.read, fs.write, data.query, data.inspect, knowledge.search]
policy:
  read: auto
  reversible: approve
  external: approve
  financial: approve
  destructive: approve
fs_roots: [company]
"""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Capture 3xx responses instead of following them."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_opener = urllib.request.build_opener(_NoRedirect())


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture()
def ws(tmp_path):
    home = tmp_path / "acme"
    (home / "company").mkdir(parents=True)
    (home / "company" / "sales.csv").write_text(SALES_CSV)
    (home / "workers").mkdir(parents=True)
    (home / "workers" / "acme-analyst.yaml").write_text(WORKER_YAML)
    (home / "workers" / "acme-gated.yaml").write_text(GATED_WORKER_YAML)
    os.environ["SWORKER_HOME"] = str(home)
    w = Workspace(str(home))
    w.ensure()
    return w


_TEST_TOKEN = "test-token-not-secret"


def _start_server(ws):
    from http.server import ThreadingHTTPServer

    store = WorkerStore(ws.state_dir)
    port = _free_port()
    httpd = ThreadingHTTPServer(
        ("127.0.0.1", port),
        lambda *a, **k: web_mod.Handler(*a, store=store, ws=ws, token=_TEST_TOKEN, port=port, **k),
    )
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, port


def _post(port: int, path: str, form: dict) -> HTTPResponse:
    url = f"http://127.0.0.1:{port}{path}"
    form = dict(form)
    form.setdefault("token", _TEST_TOKEN)
    data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        return _opener.open(req)
    except HTTPError as e:  # 4xx/5xx still carry a response
        return e


def _get(port: int, path: str) -> HTTPResponse:
    try:
        return _opener.open(f"http://127.0.0.1:{port}{path}")
    except HTTPError as e:
        return e


def _body(resp) -> str:
    return resp.read().decode("utf-8", "replace")


def test_index_lists_workers_and_run_form(ws):
    httpd, port = _start_server(ws)
    try:
        resp = _get(port, "/")
        assert resp.status == 200, resp.status
        html = _body(resp)
        assert "Sovereign AI Worker" in html
        assert "New run" in html
        assert "acme-analyst" in html
        assert "acme-gated" in html
        # JSON API works
        jr = _get(port, "/api/runs")
        assert jr.status == 200
        assert jr.headers["Content-Type"].startswith("application/json")
    finally:
        httpd.shutdown()


def test_submit_run_and_view_success(ws):
    httpd, port = _start_server(ws)
    try:
        resp = _post(port, "/run", {"worker": "acme-analyst",
                                    "request": "What was total Q2 revenue?"})
        assert resp.status == 303, resp.status
        loc = resp.headers["Location"]
        assert "run_id=" in loc
        run_id = loc.split("run_id=")[1]

        page = _get(port, f"/run?run_id={run_id}")
        assert page.status == 200
        html = _body(page)
        assert "SUCCESS" in html
        assert "188500" in html
        assert "Evidence" in html
        assert "Audit trail" in html
    finally:
        httpd.shutdown()


def test_invalid_submit_rejected(ws):
    httpd, port = _start_server(ws)
    try:
        resp = _post(port, "/run", {"worker": "", "request": ""})
        assert resp.status == 400
    finally:
        httpd.shutdown()


def test_verify_page_runs_derived_checks(ws):
    httpd, port = _start_server(ws)
    try:
        resp = _post(port, "/run", {"worker": "acme-analyst",
                                    "request": "What was total Q2 revenue?"})
        run_id = resp.headers["Location"].split("run_id=")[1]

        # Fallback runs now auto-derive recompute_sum checks; /verify should run
        # them and report ALL PASSED (the derived total re-matches the source).
        v = _get(port, f"/verify?run_id={run_id}")
        assert v.status == 200
        body = _body(v)
        assert "ALL PASSED" in body
        assert "recompute_sum" in body
        assert "no verification checks declared" not in body
    finally:
        httpd.shutdown()


def test_state_change_without_token_is_rejected(ws):
    httpd, port = _start_server(ws)
    try:
        # No token -> 403 regardless of valid payload.
        resp = _post(port, "/run", {"worker": "acme-analyst",
                                    "request": "What was total Q2 revenue?",
                                    "token": ""})
        assert resp.status == 403, resp.status
        # And a wrong token also fails.
        wrong = _post(port, "/run", {"worker": "acme-analyst",
                                     "request": "x", "token": "nope"})
        assert wrong.status == 403, wrong.status
    finally:
        httpd.shutdown()


def test_state_change_with_cross_origin_is_rejected(ws):
    httpd, port = _start_server(ws)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/run",
            data=urllib.parse.urlencode(
                {"worker": "acme-analyst", "request": "x", "token": _TEST_TOKEN}
            ).encode(),
            method="POST",
            headers={"Origin": "http://evil.example.com"},
        )
        resp = _opener.open(req)
        assert resp.status == 403, resp.status
    except HTTPError as e:
        assert e.code == 403, e.code
    finally:
        httpd.shutdown()


def test_approval_resume_loop_with_token(ws):
    httpd, port = _start_server(ws)
    try:
        resp = _post(port, "/run", {"worker": "acme-gated",
                                    "request": "What was total Q2 revenue?"})
        assert resp.status == 303, resp.status
        run_id = resp.headers["Location"].split("run_id=")[1]

        store = WorkerStore(ws.state_dir)
        pending = ApprovalManager(store).pending(run_id)
        assert pending, "expected a pending approval"
        appr_id = pending[0]["id"]

        ar = _post(port, "/approve", {"appr_id": appr_id})
        assert ar.status == 303, ar.status
        rr = _post(port, "/resume", {"run_id": run_id})
        assert rr.status == 303, rr.status

        final = _get(port, f"/run?run_id={run_id}")
        assert final.status == 200
        assert "SUCCESS" in _body(final)
    finally:
        httpd.shutdown()


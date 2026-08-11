# Sovereign AI Worker — `sworker`

A **local-first AI worker platform**. An "AI employee" you give a YAML identity,
a set of tools, and a permission policy. It executes real work against your
local files (no cloud, no model API required to run), records every step in an
append-only audit log, and **never states a number it didn't derive** — every
figure a run produces is independently re-verified from source data.

```
REQUEST → INTENT → PLAN → ACTION → TOOL → OBSERVATION → EVIDENCE →
VERIFICATION → ARTIFACT → APPROVAL → FINAL → AUDIT
```

Verified on **Python 3.14.6** (Homebrew, `/opt/homebrew/bin/python3.14`). Core
has **zero third-party dependencies**; the only optional dep is
[Hermes Atlas](https://github.com/NousResearch/hermes-atlas) for *compiled*
company-knowledge retrieval (it degrades to labelled grep without it).

---

## Why it's built this way

- **Decomposition does not launder risk.** `DecompositionGuard` remembers a risk
  ceiling a human has already rejected or left pending in a run, and blocks any
  equal-or-higher-risk action from sneaking in afterwards — so an agent refused
  "send the email" can't get there via "write the email to a file" then
  "shell: sendmail". This guarantee only holds because risk classification
  itself is **static and fails closed**, not keyword matching:
  - `python.run` is classified by parsing the submitted code with `ast` and
    walking the real import/call graph. `subprocess`, `os.system`, `os.popen`,
    `socket`, `urllib`, `requests`, `httpx`, `ftplib`, `smtplib`, `ctypes`, … are
    EXTERNAL; `shutil.rmtree`, `os.remove`, `os.unlink`, `Path.unlink`, … are
    DESTRUCTIVE. Any `ast.parse` failure, any dynamic `eval`/`exec`/`compile`/
    `__import__`/`getattr` with a non-literal argument, or any import/call the
    walker doesn't positively recognise is escalated to the **highest tier the
    tool can reach** — it never silently defaults to the safe floor.
  - `shell.exec` resolves `argv[0]` (already allowlist-checked) and additionally
    floors interpreter binaries — `python3 -c "…"`, `bash -c "…"`, `perl`, `node`,
    `ruby`, `osascript`, … — at EXTERNAL regardless of the rest of the argv, since
    their behaviour can't be verified from a command line the way a fixed-purpose
    binary like `ls` or `cat` can.
  - See `docs/SECURITY.md` for the honest security model, its limits, and the
    fail-closed contract.
- **Nothing is fabricated.** No language model? The engine falls back to a
  deterministic plan that does real retrieval over real files and says plainly,
  in the artifact, that it ran without a model. A tool fails → the step is
  recorded as failed.
- **Evidence is real.** `EvidenceLedger` mints evidence only from actual tool
  observations, each carrying a `source_ref` (file + sha256) — never model
  prose.
- **Every stated number is re-derived.** After execution, the engine turns each
  computed `data.query` figure into a `recompute_sum` verification check that
  re-sums the same source rows and compares to the derived value. A run is
  `PARTIAL_SUCCESS` if any check fails — it does not quietly keep the nicer
  number.

---

## Quick start

```bash
# 1. Interpreter — Homebrew Python 3.14 (the platform runs on 3.10+, tested on 3.14.6)
/opt/homebrew/bin/python3.14 --version

# 2. Venv + install (editable, zero deps)
cd sovereign-worker
/opt/homebrew/bin/python3.14 -m venv .venv
. .venv/bin/activate
pip install -e .

# 3. Scaffold a workspace anywhere
python -m sworker init /tmp/acme
```

> **macOS env gotcha.** Hermes' shell leaks `PYTHONPATH`/`PYTHONHOME` (pointing
> at a different Python) into subprocesses. If you get `bad interpreter` /
> `SIGABRT` / import errors when launching the server, **strip both vars**:
> ```bash
> env -u PYTHONPATH -u PYTHONHOME /opt/homebrew/bin/python3.14 -m sworker ...
> ```
> This is why every command below is prefixed that way.

### Seed the demo company

```bash
mkdir -p /tmp/acme/company /tmp/acme/workers
cat > /tmp/acme/company/sales.csv <<'CSV'
region,quarter,revenue,orders
North,Q1,42000,1320
North,Q2,51000,1480
South,Q1,31000,980
South,Q2,35500,1100
Online,Q1,88000,4200
Online,Q2,102000,5100
CSV

cat > /tmp/acme/workers/acme-analyst.yaml <<'YAML'
name: acme-analyst
role: Acme Coffee business analyst
instructions: |
  Compute figures from the CSVs with data.query; never state a number you did
  not derive. Write a markdown report that cites source totals.
tools: [fs.list, fs.read, fs.write, data.query, data.inspect, knowledge.search]
policy:
  read: auto
  reversible: auto
  external: approve
  financial: approve
  destructive: approve
fs_roots: [company]
YAML
```

### Run a request

```bash
SWORKER_HOME=/tmp/acme \
  env -u PYTHONPATH -u PYTHONHOME /opt/homebrew/bin/python3.14 -m sworker \
  run acme-analyst "What was total Q2 revenue?"
```

Output:

```
================================================================
RUN #1  SUCCESS
----------------------------------------------------------------
SUCCESS; 4 action(s) executed; 0 failed; 4 evidence item(s); 1 artifact(s);
computed: sum(revenue)=188500.0 over 3/6 rows
```

`Q2 = 51000 (North) + 35500 (South) + 102000 (Online) = 188500`. The derived
total is written into the artifact at `artifacts/q2_revenue_report.md` and
re-verified from `sales.csv` by an auto-generated `recompute_sum` check.

---

## CLI reference

| command | what it does |
|---|---|
| `init <home>` | scaffold a workspace (creates `company/`, `workers/`, `.state/`) |
| `workers` | list workers |
| `show <name>` | show worker identity + policy |
| `run <worker> "<request>"` | execute a request end-to-end |
| `runs` / `run-info <id>` / `audit <id>` | inspect runs + replay the audit trail |
| `approve <id>` / `deny <id>` | decide a pending approval |
| `resume <run_id>` | continue a run after approval |
| `learn <run_id> <name>` | capture a run as a versioned, diffable procedure |
| `proc` | list captured procedures |
| `sched` | manage cron schedules |
| `verify <run_id>` | run a run's verification checks |
| `web --port 8777` | launch the local web UI (binds `127.0.0.1` only) |

Everything reads/writes the same local store — `sqlite` fast index +
`audit.jsonl` append-only truth under `<home>/.state/`. No separate database,
nothing leaves the machine.

---

## Web UI

```bash
SWORKER_HOME=/tmp/acme \
  env -u PYTHONPATH -u PYTHONHOME /opt/homebrew/bin/python3.14 -m sworker web --port 8777
# open http://127.0.0.1:8777
```

On startup the server prints a **per-session token** to stdout:

```
Sovereign AI Worker UI on http://127.0.0.1:8777  (Ctrl-C to stop)
session token: A1d2IzydUVOo5C5nxi8lWWBP1lwQCIKHd_sLStVHhDs
(pass it as ?token=... on state-changing requests, or X-SW-Token header)
```

Binding to `127.0.0.1` is **not** a CSRF defense — any page in the same browser
could otherwise POST to `/approve` or `/resume` with no token. So every
state-changing request (`/run`, `/approve`, `/deny`, `/resume`, `/verify`)
requires that token (as `?token=` or the `X-SW-Token` header) **and** a
same-origin `Origin`/`Referer`. Requests failing either check get `403`. The
token is embedded in the page's forms automatically, so clicking buttons in the
UI needs nothing extra; only direct/scripted POSTs must supply it. Pass
`--token <fixed>` to use a stable token (e.g. behind a reverse proxy that already
enforces auth).

A single-file `http.server` app (stdlib only) that lets you:

- submit a request to a worker and watch the run appear;
- replay a run's audit trail, evidence (with `source_ref`s), and artifacts;
- **approve / reject a pending approval and resume the run** — the full gate loop
  over HTTP;
- run a run's verification checks.

JSON API: `GET /api/runs`.

---

## Tests

Real integration tests — they build a temp workspace, seed CSV data, run the
engine **without a language model** (deterministic fallback), and assert on the
persisted run/evidence/artifact/verification records. No mocks, no cloud.

```bash
cd sovereign-worker
env -u PYTHONPATH -u PYTHONHOME /opt/homebrew/bin/python3.14 -m pytest tests/ -q
# 29 passed
```

Coverage:

- `test_engine.py` — lifecycle, evidence minting, audit reconstruction, the
  deterministic fallback, and **auto-derived + passing verifications**
  (`recompute_sum` re-matches the source: Q2 → `188500.0`).
- `test_verify_and_procedures.py` — deterministic checks, scheduler cron math,
  procedural memory capture.
- `test_web.py` — live HTTP: index, submit→redirect→run page, the approve→resume
  loop, and the verify page.
- `test_knowledge.py` — the Atlas bridge: **BLACK** (Atlas absent → labelled
  grep, never fabricated) and **COMPILED** (fake `hermes_atlas` injected so the
  claim-retrieval branch runs end to end).

### Bugs found & fixed during the build (so you don't re-hit them)

1. **`/tmp` symlink escapes the sandbox.** On macOS `/tmp` → `/private/tmp`.
   `os.path.relpath` produced `../../private/tmp/...` which the verification
   path guard rejected as "escapes workspace". Fix: `realpath` *both* sides
   before `relpath` (engine `_derive_verifications`; `ToolContext.resolve`
   already did this).
2. **Derived `data.query` figures lost their filter.** The verification spec was
   built from `data.query`'s `data` dict, which omits `where`/`group_by`, so the
   recompute summed *all* rows (got `349500` vs derived `188500`) → `FAIL`.
   Fix: thread the original tool `args` into the computed record and prefer
   `args["where"]`/`args["group_by"]` when deriving checks.
3. **Quarter token broke on punctuation.** `"Q1?"` failed `q in low.split()`.
   Fix: `tokens = re.sub(r"[^a-z0-9]+", " ", low).split()` then match `q1`–`q4`.
4. **Cron dow translation.** `next_fire` didn't translate cron's 0=Sun..6=Sat to
   Python's 0=Mon..6=Sun. Fix: `(d-1)%7`.
5. **`page()` returned `bytes` but call sites did `.encode()`.** Type mismatch
   in `web.py`; now `page()` returns `str`, `_send` encodes once.
6. **Tests asserted the wrong shape.** `Workspace` props return `str` not
   `Path` (`Path(ws.X)`), `run_check` needs `ws.root` not `str(ws)`, evidence
   provenance values are lowercase enum strings. Corrected in the tests, not the
   code.

---

## Architecture

```
sworker/
  config.py      Workspace + WorkerConfig (policy, fs_roots, timeout)
  models.py      RunStatus / ActionStatus / StepStatus / RiskLevel / Provenance
                 VerificationOutcome, Record (to_dict/from_dict), Task/Plan/Run
  store.py       WorkerStore: sqlite index + JSONL audit (reconstructable runs)
  tools/         base (Tool/ToolContext/risk floor), fs, exec, http, git,
                 browser, message, data (query/inspect), knowledge (Atlas bridge)
  permissions.py PermissionEngine (policy + tool risk = floor)
  approvals.py   ApprovalManager (immutable approve/reject records)
  evidence.py    EvidenceLedger (mint from real observations only)
  verify.py      deterministic checks: recompute_sum/delta/row_count/
                 file_exists/artifact_contains_evidence/totals_match_source
  engine.py      WorkerEngine lifecycle + deterministic fallback + verification
  procedures.py  learn_from_run -> versioned, diffable YAML procedures
  scheduler.py   parse_cron / next_fire
  knowledge.py   Hermes Atlas bridge (compile company/*.md -> claim retrieval)
  web.py         local-first web UI (functional: run/approve/resume/verify)
  cli.py         command line
```

**Design commitments:** local-first, no cloud APIs; the model proposes and the
engine disposes; nothing fabricated; verification re-derives from source with no
model in the loop; the store is sqlite fast-index + JSONL truth so any run is
byte-for-byte reconstructable.

## Security

The honest security model — permission/risk classification (and its fail-closed
behaviour), the execution sandbox limits, HTTP SSRF surface, git egress, and the
web UI's token + same-origin CSRF defense — is documented in
[`docs/SECURITY.md`](docs/SECURITY.md). Read it before deploying a worker that
can reach the network or push to a remote.

# `sworker/sales` — Sovereign AI Sales Worker (Consulting Edition) boundary layer

This package is **not** a re-implementation of Sovereign Worker. It is the thin
integration boundary that projects a **Sovereign AI Systems Engineering
consulting** sales domain (markdown knowledge + the `Experiment_Ledger` sqlite
database) into Sovereign Worker's existing execution engine — five-tier
permissions, `EvidenceLedger`, `verify.py` checks, `procedures.py`,
`scheduler.py` and the sqlite + hash-chained `audit.jsonl` store are all reused
as-is.

This repository (`sovereign-sales-worker`) is a clone of `sovereign-worker`
retargeted to run a *real* consulting sales workflow. The original generic
platform is left untouched; every change lives under `sworker/sales/`.

The authoritative design document is `docs/SALES_INTEGRATION.md`. This README is
the map of the package itself.

## Domain (this edition)

- **Offer:** *Sovereign AI Workflow & Knowledge Systems Audit* — a $3,500 flat,
  two-week audit that maps a client's operations workflow and quantifies friction
  (time + duplicate software spend), then recommends what they can own and run
  locally.
- **ICP:** 7 ranked industries (top = Professional Services Firms). Compiled from
  `corpus/Industry_Ranking.md`.
- **Daily targets:** 20 prospects researched, 5 outreach sent, 10 follow-ups,
  2 discovery calls scheduled, 1 completed. Parsed from
  `corpus/Metrics_Single_Source_of_Truth.md`.
- **Knowledge corpus** ships *bundled* in `sworker/sales/corpus/` so the repo is
  fully self-contained (no external sibling folder required). Resolution order:
  `SOVEREIGNSALES_ROOT` env → legacy `DAILYSALESOS_ROOT` env →
  `<workspace>/sales_knowledge/` → bundled corpus.

## Layout

| Module | Responsibility |
|---|---|
| `models.py` | Sales ontology as dataclasses (`Lead`, `Company`, `Contact`, `Qualification`, `PipelineStage` (15 members), `ClaimTier`, …). |
| `schema.py` | `ensure_schema()` — idempotent, **additive** DDL. Never drops or alters the pre-existing `prospects`/`experiments`/`deals` tables. |
| `repository.py` | `SalesRepository` — the **single writer** to the sales tables. Enum round-trip, FK nullification, read-only `raw()`. |
| `pipeline.py` | 14 documented CRM stages + split `WON`/`LOST` → 15 enum members; transition legality via `can_move`. |
| `qualification.py` | Deterministic opportunity score from `Discovery_Rubric.md`'s formula. Refuses to score a lead with no evidence. |
| `evidence.py` | `SalesEvidence.attach` — evidence only from real observations; `source_ref` is `path#sha256:…` or a run/observation ref. |
| `knowledge.py` | The **compiler**: parses the consulting markdown (ICP, offer, targets, follow-up sequences) into the ontology, recording `source_doc` + line for every value. |
| `discovery.py` / `research.py` / `outreach.py` / `followup.py` / `metrics.py` | Domain functions used by the tools (local-only; never egress). |
| `checks.py` | 5 `@check` hooks: `sales_score_recomputes`, `sales_evidence_has_source`, `sales_outreach_approved_first`, `sales_pipeline_legal`, `sales_metrics_match_ledger`. |
| `tools/base.py` | 16 `Sales*` `Tool` subclasses at declared risk tiers, opt-in to the registry (`build_registry()` → 40 tools total). |
| `cli.py` | `sworker sales …` group: `init`, `seed`, `icp`, `pipeline`, `lead`, `outreach`, `followups`, `metrics`, `verify`, `brief`, `daily-run`, `templates`. |
| `web.py` | `/api/v1/sales` endpoints + the `/sales` page, on the existing stdlib server. |
| `templates/` | Worker YAMLs (`sales_researcher`, `sales_outreach`, `sales_followup`, `sales_qualifier`, `sales_analyst`, `sales_strategist`) + `DAILY_RESEARCH.yaml` / `DAILY_SALES_RUN.yaml` procedures. |
| `corpus/` | Bundled consulting knowledge (ICP, offer, metrics, pipeline, rubric, follow-up, claims). |

## Tools (actual names)

All 16 sales capabilities are exposed with a `sales_` prefix so they coexist with
the core registry:

`read` tier — `sales_pipeline_list`, `sales_evidence_explain`, `sales_lead_detail`,
`sales_stale_leads`, `sales_pipeline_summary`, `sales_followup_due`, `sales_metrics`.
`reversible` — `sales_discover`, `sales_research`, `sales_qualify`, `sales_move_stage`,
`sales_draft_outreach`, `sales_schedule_followup`.
`external` — `sales_approve_draft`, `sales_record_sent`.
`financial` — `sales_bulk_send`.

With the default policy (`external: approve`, `financial: approve`) a worker
discovers, researches, scores, drafts and schedules automatically and **cannot
send without a human approval**. Separation of duties is enforced by worker
`tools:` allowlists — the researcher/analyst/qualifier have no `sales_approve_draft`
/ `*_sent` tools; outreach has no discover/research tools; the strategist may
stage + approve but cannot record a send.

## Running

```bash
# from the repo root; core has zero third-party deps, Python 3.14
cd sovereign-sales-worker
export SOVEREIGNSALES_ROOT="$PWD/sworker/sales/corpus"
export DAILYSALESOS_LEDGER="/tmp/salestest/company/Experiment_Ledger/experiments.db"

python3.14 -m sworker sales init --force
python3.14 -m sworker sales seed
python3.14 -m sworker run sales_researcher "execute DAILY_RESEARCH" \
    -p DAILY_RESEARCH -i source=candidates.csv -i limit=20
python3.14 -m sworker sales daily-run --source candidates.csv --limit 20
python3.14 -m sworker sales brief
python3.14 -m sworker verify --run <run_id>
```

## Tests

`env -u PYTHONPATH -u PYTHONHOME python3.14 -m pytest tests/ -q -p no:cacheprovider`
→ **512 passed** (490 baseline inherited + sales tests; includes the real-world
validation harness suite in `tests/test_sales_rwv.py`).

## Real-world validation harness

The `rwv` subcommand drives the **actual** app (discover → research → qualify →
draft → explain) on a labelled fixture and reads the real ledger back. It does not
reimplement the pipeline. Use it to answer — with evidence — *who to talk to,
why, what to offer, what next*, and to record human A/B/C/D judgements in a
separate store that never mutates the automated score.

```bash
python3.14 -m sworker sales rwv run --limit 50
python3.14 -m sworker sales rwv report --top 15 --audit 2
python3.14 -m sworker sales rwv human-classify <lead_id> A --reason '...'
python3.14 -m sworker sales rwv disagreement
python3.14 -m sworker sales rwv audit --lead-id <lead_id>
```

See `docs/REAL_WORLD_VALIDATION.md` for the honest validation report (what works,
where it fails, next engineering work). The fixture is synthetic — this proves the
mechanics, not real-world fit.

## Constraints (non-negotiable)

- **Zero third-party deps** in the core; this package is stdlib-only too.
- **Fail-closed.** Unknown tool, unknown risk key, or unparseable input → deny,
  never guess. Evidence requires a real `source_ref`; qualification refuses
  no-evidence leads.
- **Ledger is additive.** Pre-existing tables are never dropped or altered.
- **Closed-world planning.** The fallback planner converts unknown tools into
  reasoning-only steps.
- **No fabrication.** Nothing in the database is unattributable; every claim is
  traceable to a `source_doc` or observation.
- **Human-in-the-loop egress.** Outreach is drafted and staged but never sent
  without an explicit human approval; the loop surfaces pending approvals rather
  than auto-egressing.

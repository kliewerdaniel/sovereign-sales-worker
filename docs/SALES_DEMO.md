# Sovereign AI Sales Worker — End-to-End Demo (Consulting Edition)

A walkthrough of the Sales Worker running the real `daily-run` loop, captured from
a clean environment. This is the artifact that makes "governed, attributable,
reproducible, independently verifiable" concrete instead of asserted. Run IDs and
evidence refs below are from an actual invocation on **2026-08-12** (no model — the
deterministic `NullInference` fallback, so the loop proves out without a live LLM).

> This edition (`sovereign-sales-worker`) is a clone of `sovereign-worker`
> retargeted to acquire **Sovereign AI Systems Engineering consulting** clients.
> The loop below is exactly the generic runtime driven by a consulting worker
> identity — nothing in it is consulting-specific engine code.

## What this proves

- Two worker instances run through one engine, with **separation of duties**
  (researcher discovers/researches/qualifies; outreach drafts/schedules — neither
  sends without the operator).
- Every figure in the report is **re-derived from the ledger** and every claim
  carries a `source_ref`.
- **External egress is held for approval**: drafts are produced but none are sent.
  The run downgrades to a *Failed sales day* badge rather than pretending the
  targets were met.
- The whole run is **reconstructable without a model** via `sworker inspect`
  / `audit` / `replay`.

## Prerequisites

```bash
# Python 3.14.6 (Homebrew). Core has zero third-party deps.
/opt/homebrew/bin/python3.14 --version

# Bundled consulting knowledge ships in the repo; point the env at it.
export SOVEREIGNSALES_ROOT="$PWD/sworker/sales/corpus"
# (legacy alias DAILYSALESOS_ROOT is also honoured for backward-compat)
```

## 1. Scaffold + seed a deterministic demo company

```bash
cd sovereign-sales-worker
export DAILYSALESOS_LEDGER=/tmp/salestest/company/Experiment_Ledger/experiments.db

python3.14 -m sworker sales init --force
# → sales workers written: sales_analyst.yaml, sales_followup.yaml,
#   sales_qualifier.yaml, sales_researcher.yaml, sales_outreach.yaml,
#   sales_strategist.yaml, DAILY_RESEARCH.yaml, DAILY_SALES_RUN.yaml
# → ICP compiled from <corpus>: 7 industries

python3.14 -m sworker sales seed
# → seeded: /tmp/salestest/company/candidates.csv (3 candidates)
# → seeded: /tmp/salestest/company/meridian_law.md
```

`seed` is pure and idempotent: running it twice yields byte-identical files, so the
demo needs no private CRM or live API. The offer (Sovereign AI Workflow &
Knowledge Systems Audit — **$3,500** flat) and the daily targets (20 researched /
5 sent / 10 follow-ups / 2 discovery scheduled / 1 completed) come from the bundled
`corpus/` markdown, never hard-coded.

## 2. Run the daily loop

```bash
python3.14 -m sworker sales daily-run --source candidates.csv --limit 20
```

Output (verbatim, trimmed):

```
✓ Discover up to 20 candidate companies from candidates.csv    (sales_discover)
✓ Research every discovered lead from permitted company sources (sales_research)
✓ Qualify every researched lead deterministically from its evidence (sales_qualify)
✓ Produce the daily sales report against the documented targets (sales_metrics)
✓ Draft a personalised outreach message for each qualified lead (sales_draft_outreach)
✓ Schedule the documented next action for each contacted/res… (sales_schedule_followup)
✓ Move each reached lead to the contacted stage (legal transitions) (sales_move_stage)
✓ Produce the daily sales report against the documented targets (sales_metrics)

================================================================
DAILY SALES REPORT
================================================================
date:          2026-08-12
failed_sales_day: True
  MISS prospects_researched   6/20
  MISS outreach_sent          1/5
  MISS followups_sent         0/10
  MISS discoveries_completed  0/1
  MISS discoveries_scheduled  0/2
  - 15 outreach draft(s) awaiting approval
pending_approvals: 15

PER-RUN SUMMARY
  sales_researcher   SUCCESS          ok=yes
    inspect: sworker inspect run_3def8575187f
    replay:  sworker replay run_3def8575187f
  sales_outreach     SUCCESS          ok=yes
    inspect: sworker inspect run_4a9ef374e275
    replay:  sworker replay run_4a9ef374e275
```

## 3. Inspect what actually happened (reconstructable without a model)

```bash
sworker inspect run_4a9ef374e275
```

The researcher pass (`run_3def8575187f`) shows the same shape at the
discover/qualify stage, and every evidence row carries a `source_ref` — e.g. the
discover evidence points at `candidates.csv#sha256:bf61c786c06a…`.

## 4. The daily brief (operator morning screen)

```bash
python3.14 -m sworker sales brief
```

```
================================================================
SOVEREIGN SALES WORKER — DAILY BRIEF
================================================================
date:              2026-08-12
failed_sales_day:  True
vs targets:
  MISS prospects_researched   6/20
  MISS outreach_sent          1/5
  MISS followups_sent         0/10
  MISS discoveries_completed  0/1
  MISS discoveries_scheduled  0/2
follow-ups due:    0
tasks due:         0
stage-SLA breaches:0
bottlenecks:
  - leads_researched: 6 of 20 target (prospects_researched)
  - outreach_sent: 1 of 5 target (outreach_sent)
  - 15 outreach draft(s) awaiting approval
pending approvals: 15
----------------------------------------------------------------
open a lead:  sworker sales lead show <id>
run the loop: sworker sales daily-run
```

## 5. The approval gate + clean draft

```bash
python3.14 -m sworker sales lead show <lead_id>   # inspect evidence + score
python3.14 -m sworker sales outreach draft <lead_id>
# → drafted; requires_approval=True; draft_id=out_…

python3.14 -m sworker sales outreach approve <draft_id> --approved-by "Daniel"
```

A generated consulting draft (verbatim):

```
there,

Looking at Acme Robotics, I noticed how Acme Robotics handles repetitive
operations and internal knowledge

I run a Sovereign AI Workflow & Knowledge Systems Audit — $3,500, two weeks —
that maps your full operations workflow and quantifies what friction is costing
in time and duplicate software spend, then recommends what you can own and run
locally.

[sequence: New Prospect / day_3 — Follow-up #1 — reference the specific signal observed; one-line nudge.]

Worth a short conversation?

Daniel
```

The draft is assembled **deterministically from stored facts only** — the offer
name + price come from `Core_Offer.md`, the sequence step from
`Follow_Up_System.md`, and the observation from real evidence (never internal
`provenance` bookkeeping). A local model may tone-rewrite the body, but
`outreach.validate_rewrite` rejects any rewrite that introduces a number not
already in the deterministic draft.

Sending is `sales_record_sent` / `sales_bulk_send`, both risk `EXTERNAL` /
`financial`, and the researcher's `tools:` allowlist excludes them entirely. To
complete egress the operator approves each draft and records the send:

```bash
sworker approve <draft_approval_id>   # operator sign-off
# record_sent is then executed by the operator, never auto-fired by the loop
```

Without that human step, the loop reports `pending_approvals: 15` and a `Failed
sales day` badge. That is **intended fail-closed behaviour**, not a defect.

## 6. Replay / audit

```bash
sworker audit run_3def8575187f    # append-only, hash-chained event log
sworker replay run_3def8575187f   # reconstruct the run from persisted records (no model)
```

The audit tail shows the hash chain intact: `evidence.recorded → artifact.created
→ step.done → run.transition → run.status → run.finished`.

## Limitations (what still needs a human or a model)

1. **A model improves, not enables.** The deterministic path runs with no LLM
   (`NullInference`). What the model *adds* is tone-rewriting outreach bodies — and
   even then `outreach.validate_rewrite` rejects any rewrite that introduces a
   number not already in the deterministic draft. Without a model, drafts are plain
   but fact-complete.
2. **Research needs a per-lead source file.** `sales_research` reads permitted docs
   under `company/`. With real per-company source files, evidence + pain points
   attach. The qualification still runs deterministically (it scores from whatever
   evidence exists; a lead with zero evidence is refused, never scored from nothing).
3. **AST classification is not a sandbox.** `python.run`/`shell.exec` risk is derived
   by static `ast` walking + allowlisting; unrecognised imports/commands escalate to
   the highest tier. This *reduces* risk; it is not a container.
4. **Qualification judgment is not guaranteed true.** A `qualification.score` is
   computed deterministically from stored evidence and re-derived by the
   `sales_score_recomputes` check — but the *truth* of a pain-point or a fit
   judgment is only as good as the source it cites. The guarantee is on the
   **evidence trail**, not on the semantic claim.
5. **Targets come from one doc.** The daily minimums are parsed from
   `corpus/Metrics_Single_Source_of_Truth.md`. If that wording drifts, the
   `parse_daily_targets` regression test (`tests/test_sales_targets_real_doc.py`)
   fails CI rather than silently degrading the badge.
6. **Still manual today.** Approval/deny and the actual send are operator actions.
   The follow-up *scheduling* is automatic per stage rule, but the actual human
   follow-up and any live send remain human-in-the-loop by design.

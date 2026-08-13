# Sovereign Worker — Control Plane UI

A world-class, production-quality web console for the **existing** Sovereign Sales Worker
runtime. It is built to make the worker feel powerful, trustworthy, and inspectable: what
the worker knows, why it decided, what it did, and what still needs a human.

> **Philosophy:** *Autonomous does not have to mean opaque. AI workers can be powerful while
> remaining inspectable, evidence-driven, and under human control.*

---

## Stack

- **Next.js 16** (App Router, Turbopack, React Server Components) · **React 19**
- **TypeScript** (strict)
- **Tailwind CSS v4** (`@theme` tokens, dark-first)
- **shadcn/ui-style primitives** on Radix (`react-dialog`, `react-dropdown-menu`, `react-tooltip`, `react-tabs`, `react-accordion`, `react-progress`, …)
- **Framer Motion** for motion · **Lucide** icons
- Zero UI dependencies that reimplement the backend. The UI only *reads* the runtime.

---

## Run it

```bash
cd ui
npm install
npm run dev          # http://localhost:3000
```

```bash
npm run build        # production build (also runs the TypeScript gate)
npm run start        # serve the production build
```

> Requires Node 22+. Node 20 is EOL and unsupported by Next 16.

---

## Data strategy — demo mode, honest boundary

The UI consumes a single typed **`Backend` adapter interface** (`src/lib/api.ts`). Two
implementations exist:

| Backend | Source | Notes |
| --- | --- | --- |
| `demoBackend` (default) | `src/lib/data/demo.ts` | Deterministic, typed dataset that **conforms exactly** to the runtime's `/api/v1` JSON contract. Clearly tagged **DEMO** in the UI. |
| `createLiveBackend(baseUrl)` | `sworker/web.py` `/api/v1` | Swap to a real runtime by setting `NEXT_PUBLIC_SOVEREIGN_API_BASE` and restarting. |

The demo dataset tells one coherent, honest story: a `sales_researcher` run that qualifies a
prospect, hits a **policy-denied** external action (egress allow-list empty), and produces a
draft outreach that **requires human approval** before any send. Every evidence row has a real
`source_ref`; every artifact has real content; nothing fake is presented as real.

No fabricated intelligence. The demo surfaces the same shapes a live `sovereign-worker`
runtime exposes.

---

## What you can inspect

| Route | What it shows |
| --- | --- |
| `/` Mission Control | Live overview: runs, evidence, artifacts, tool failures, and the "who to talk to today" pipeline snapshot. |
| `/runs` | Every execution — filter by status, search, sort. |
| `/runs/[id]` | **Run Detail**: the 13-stage lifecycle spine (Request → Intent → Plan → Step → Action → Tool → Observation → Evidence → Claim → Verify → Artifact → Approval → Final → Audit), the event timeline, and the "why" panel that resolves any record to its provenance. |
| `/replay/[id]` | **Replay**: step through a run from the hash-chained audit trail. Play/pause/scrub. No model re-run. |
| `/evidence` | The provenance database — every observed fact, filterable by provenance tier. |
| `/artifacts` | Outputs of computation (reports, drafts, decisions) with sha256. |
| `/approvals` | The human-in-the-loop gate — every pending/approved/rejected decision with risk + evidence. |
| `/policy` | What each worker is allowed to do. Version-controlled YAML, default-deny. |
| `/tools` | The tool registry — risk level, approval requirement, telemetry. |
| `/audit` | Hash-chain integrity status + security events (policy blocks, approvals, verifications). |
| `/workers` | Worker identities: role, knowledge, policy boundary. |
| `/prospects` | Sales pipeline — deterministic, evidence-re-derivable lead scores. |
| `/prospects/[id]` | A prospect: qualification breakdown, pain points, outreach drafts, evidence, company, contacts. |
| `/settings` | Backend connection + the design philosophy. |

A **command palette** (⌘/Ctrl+K) provides global navigation. Theme toggle is top-right.

---

## Architecture

```
src/
  app/                 # routes (App Router)
    page.tsx           # Mission Control
    runs/              # explorer + [id] detail
    replay/            # [id] replay interface
    evidence/ artifacts/ approvals/ policy/ tools/ audit/ workers/
    prospects/         # list + [id] detail
    settings/
  components/
    layout/            # app shell: sidebar, topbar, demo notice
    providers/         # backend + command-palette + theme context
    run/               # execution graph, timeline, stage detail
    ui/                # primitives (Badge, Card, RefId, …) on Radix
  lib/
    types.ts           # typed domain model — mirrors the Python runtime exactly
    api.ts             # Backend interface + demo/live implementations
    domain.ts          # tone/label maps, formatters
    run-graph.ts       # derives lifecycle spine from a RunBundle
    use-async.ts       # data-loading hook
    nav.ts             # sidebar + palette nav
    data/demo.ts       # deterministic, contract-conforming demo dataset
```

### Why types mirror the runtime

`src/lib/types.ts` is the single source of truth for shapes. The field names, enums
(`RiskLevel`, `RunStatus`, `PipelineStage`, `ClaimTier`, `Provenance`, …), and nested
records (`RunBundle`, `LeadDetail`, `ToolSpec`, `WorkerConfig`) are the literal JSON the
`sovereign-worker` web server emits. This means the **live backend is a drop-in**: only
`createLiveBackend` changes (it `fetch`es `/api/v1/*`); none of the components do.

---

## Verification

- `npx tsc --noEmit` — type gate (strict).
- `npm run build` — production build (compiles + type-checks all 15 routes).
- Routes are statically prerendered where possible; `/runs/[id]`, `/prospects/[id]`, and
  `/replay/[id]` are server-rendered on demand.

---

## Honest limitations

- The live backend maps to the documented `/api/v1` endpoints; some aggregate endpoints
  (e.g. `/evidence`, `/artifacts`, `/approvals`) are expected to be derived server-side from
  the ledger and are stubbed in `createLiveBackend` with sensible paths.
- The demo dataset is intentionally small (one fully-detailed run + a couple of stubs) to
  keep the story coherent and the shapes honest — not to fake volume.
- ESLint under ESLint 9's `FlatCompat` has a known circular-config loader bug in this
  scaffold; `next build`'s TypeScript gate is the authoritative check and passes.

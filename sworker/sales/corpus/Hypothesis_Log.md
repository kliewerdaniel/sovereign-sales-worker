# Hypothesis Log — Claim Quality Tiers

Every claim about a prospect carries a tier. The tier determines how much the
system is allowed to trust it and what confidence it contributes.

## Tiers (high to low)

1. **CLIENT_VERIFIED** — the prospect stated it directly (email, call, form).
2. **OBSERVED** — discovered in a source file the worker actually read; cited.
3. **HYPOTHESIS** — a reasonable inference from observed evidence.
4. **CLAIM** — asserted without a source; treated as low-confidence until backed.

## Rules

- No outreach statement may be a CLAIM about the prospect. Every factual claim
  about a company must trace to OBSERVED evidence with a source_ref.
- INFERRED conclusions may appear in research reports, clearly labelled, and must
  be separated from OBSERVED facts.
- HYPOTHESIZED items are phrased as discovery questions, never as facts.
- A claim promoted to CLIENT_VERIFIED requires >= 2 independent observed sources
  or direct prospect confirmation.

This is the sales layer's mapping onto the sworker `EvidenceLedger` provenance
model (see `sworker/sales/evidence.py`).

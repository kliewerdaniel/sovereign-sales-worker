# CRM Pipeline

The pipeline is a checked state machine. Each stage has entry criteria and a
maximum duration (SLA). Moving a lead is a logged, append-only transition — history
is never rewritten.

| # | Stage | Entry criteria | Max days |
|---|-------|----------------|----------|
| 1 | prospect | Name, company, source recorded | — |
| 2 | contacted | First outreach sent | 7 |
| 3 | responded | Any reply received (even "no") | 3 |
| 4 | discovery_scheduled | Agreed to discovery call; date known | — |
| 5 | discovery_completed | Call done; notes, pain points, score, next step recorded | 1 |
| 6 | qualified | Meets audit criteria (clear pain + decision maker + budget) | 5 |
| 7 | audit_in_progress | Signed agreement + payment received | 14 |
| 8 | proposal_sent | Audit delivered, implementation proposed | 21 |
| 9 | negotiation | Client negotiating scope/price | — |
| 10 | won / lost | Agreement signed / explicit loss with reason | — |
| 11 | onboarding | Contract signed + payment | — |
| 12 | implementation | Kickoff complete; active build | — |
| 13 | completed | Delivered + accepted | — |
| 14 | expansion | Upsell / retainer opportunity | — |

Lost is reachable from any non-terminal stage. WON -> ONBOARDING is the only
forward exit from a terminal stage.

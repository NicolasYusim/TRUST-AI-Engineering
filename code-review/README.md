# Code review checklists

Use the checklist for every principle affected by a change, plus the mandatory
security/privacy overlay.

| Change | Required review |
|---|---|
| Model, prompt, retrieval, or context | T1, U, T2 |
| API/fallback/runtime behavior | R, U |
| Structured output or state | S |
| Tool, agent, or side effect | S, R, T1, T2, overlay |
| Data collection or logging | T1, overlay |
| New AI component | All five, overlay, `trust.yaml` |

- [`traceability-checklist.md`](traceability-checklist.md)
- [`resilience-checklist.md`](resilience-checklist.md)
- [`unit-economics-checklist.md`](unit-economics-checklist.md)
- [`state-structure-checklist.md`](state-structure-checklist.md)
- [`testability-checklist.md`](testability-checklist.md)
- [`../docs/security-privacy-overlay.md`](../docs/security-privacy-overlay.md)

The pull-request template mirrors these controls. A reviewer may approve a
documented exception only when it has an independent approver, expiry,
compensating control, and risk acceptance recorded under
[`../exceptions/`](../exceptions/). A component change is not ready until both
`./trust lint` and `./trust verify` pass.

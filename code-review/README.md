# Code Review Checklists

Each checklist maps to one T.R.U.S.T. axiom. Use them during PR review for any change that touches an AI component.

## How to Use

You don't need all five checklists for every PR. Pick the ones relevant to what changed:

| What changed | Checklists to use |
|---|---|
| Prompt or model version | T1, T2 |
| API call logic | R, U |
| Response parsing / output handling | S |
| New AI feature | All five |
| Infra / fallback logic | R |
| Eval pipeline | T2 |

## The One Meta-Question

Before opening any checklist, ask:

> *"If this AI component disappeared right now, what would break, and would we know?"*

If the answer is "everything would break silently" — start with **R**.  
If the answer is "we wouldn't know" — start with **T1** and **T2**.

---

- [`traceability-checklist.md`](traceability-checklist.md)
- [`resilience-checklist.md`](resilience-checklist.md)
- [`unit-economics-checklist.md`](unit-economics-checklist.md)
- [`state-structure-checklist.md`](state-structure-checklist.md)
- [`testability-checklist.md`](testability-checklist.md)

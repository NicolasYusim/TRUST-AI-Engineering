# Agentic control-plane blocking

**Evidence basis:** `measured` on four committed adversarial action plans and one
valid plan in `tests/test_examples.py`.

## Question

Does the reference control plane block plans that lack confirmation, exceed a
per-tool limit, request a forbidden tool, or target an unauthorized ticket before
any side effect?

Confirmation is bound to authenticated user, tenant, complete plan, and
idempotency key. A tenant-scoped idempotency key is also bound to the canonical
plan payload; reuse with another payload is rejected rather than silently
treated as a replay.

## Result

| Metric | Result |
|---|---:|
| Adversarial plans | 4 |
| Adversarial plans blocked before effects | 4 |
| Unauthorized-action block rate | 1.00 |
| Valid plans applied | 1 |
| Duplicate effects after replaying the idempotency key | 0 |
| Reused confirmation accepted for a changed plan | 0 |
| Idempotency-key payload conflicts blocked | 1 |

Result artifact:
[`results/agentic-control.json`](results/agentic-control.json).

## Limits

The store is in-memory and transactional. The result does not prove atomicity
across external APIs; production adapters need transactions or compensation.

# Support-triage candidate gate

**Evidence basis:** `measured` on
[`../evals/support-triage-v1.jsonl`](../evals/support-triage-v1.jsonl), a committed
synthetic repository fixture.

## Question

Does the candidate add account and shipping routing without regressing billing,
technical, or unknown/manual-review behavior?

## Result

| Metric | Baseline | Candidate |
|---|---:|---:|
| Accuracy | 0.60 | 1.00 |
| Review-policy accuracy | 0.60 | 1.00 |
| Predeclared blocking accuracy | 0.90 | 0.90 |
| Gate | fail | pass |

Result artifact:
[`results/support-triage.json`](results/support-triage.json).

## Limits

The fixture is synthetic and small. The result proves the repository gate and
candidate behavior on these cases only; it is not production-quality evidence.

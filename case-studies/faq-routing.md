# FAQ routing call reduction

**Evidence basis:** `measured` on a committed synthetic query sequence exercised
by `tests/test_examples.py`.

## Question

Can deterministic published FAQ routing and scoped caching reduce generator calls
without caching unverified generated output?

## Result

| Metric | Always-generate baseline | Reference router |
|---|---:|---:|
| Requests | 10 | 10 |
| Generator calls | 10 | 2 |
| Generator-call reduction | 0.00 | 0.80 |
| Generated answers placed in reusable cache | 10 | 0 |

Result artifact: [`results/faq-routing.json`](results/faq-routing.json).

## Limits

The result is not a currency saving, production hit rate, or semantic-quality
claim. Token-set similarity and the query mix are illustrative fixtures.

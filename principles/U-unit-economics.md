# U — Utility & Bounds

> Every AI call has an expected user or business benefit and explicit cost, latency, and resource bounds. Choose the lowest-cost path that meets measured quality and safety requirements.

**Review question:** Is this the cheapest and fastest path that meets the required quality and safety?

## Intent

The goal is not to minimize model spend in isolation. It is to select the
lowest-cost, lowest-latency architecture that meets a declared quality and safety
target for the use case.

A simple task can still justify AI when it creates sufficient value. A complex
task may not justify AI if latency, privacy, or failure cost outweighs that value.

## Required controls

Declare and observe:

- expected product outcome and a measurable success signal;
- input, output, tool, and reasoning/resource caps where supported;
- latency SLO and timeout budget;
- monthly or per-request budget with an owner;
- model/routing policy and the evidence used to select it;
- cache scope, freshness, invalidation, tenant boundary, and validation policy;
- actual cost and latency by component, route, and outcome.

Operational numeric settings use the evidence labels defined in
[`docs/evidence-labels.md`](../docs/evidence-labels.md).

## Optimization order

1. Remove calls that do not improve the product outcome.
2. Use deterministic lookup or computation when it meets the target.
3. Reduce context to relevant, authorized evidence.
4. Bound output and tool loops.
5. Route among evaluated models or local systems.
6. Cache only when identity, context, tenant, freshness, and safety permit it.
7. Re-evaluate after provider, price, traffic, or product changes.

## Caching

A semantic match is not proof that a cached answer is valid for the current
tenant, locale, policy version, conversation state, or time. Cache keys and
filters must encode every dimension that changes answer validity. Generated
answers should not become durable policy merely because they were cached.

## What this principle does not guarantee

- that the smallest model is cheapest at the system level;
- that a universal similarity threshold transfers between datasets;
- that `max_tokens` is prepaid capacity rather than a safety bound;
- that local inference is cheaper at a particular traffic level;
- that lower cost preserves quality without an evaluation.

## Review checklist

Use [`code-review/unit-economics-checklist.md`](../code-review/unit-economics-checklist.md).
The offline reference implementation is
[`examples/unit-economics/correct.py`](../examples/unit-economics/correct.py).

# R — Resilience & Ownership

> Every AI dependency has explicit failure semantics, bounded recovery behavior, an observable service objective, and a named owner. The system fails closed or degrades deliberately according to consequence.

**Review question:** How does this component fail or degrade, and who owns the outcome?

## Intent

An AI call combines ordinary distributed-system failures with quality failures:
timeouts, quotas, provider outages, malformed output, unsupported claims, unsafe
actions, and distribution shift.

Resilience does not mean hiding every failure or returning a plausible answer at
all costs. A clear unavailable response can be safer than a lower-quality
fallback. The required behavior is deliberate, observable, bounded, and owned.

## Failure contract

Every component declares:

- user-visible behavior for timeout, refusal, invalid output, and unavailable
  dependencies;
- which failures are retryable and the retry/time budget;
- whether fallback is equivalent, degraded, cached, human-routed, or forbidden;
- an SLO and telemetry for success, latency, invalid output, and fallback use;
- a named operational owner and incident/runbook reference where required.

## Recovery rules

- Retry only transient failures and cap both attempts and total elapsed time.
- Use idempotency keys for retries that can reach side-effecting systems.
- Treat cross-provider fallback as a separate product path with its own eval.
- Do not serve stale cached output where freshness affects safety or correctness.
- Prefer fail-closed behavior for authorization, consequential actions, and
  unknown policy state.
- Exercise fallback and recovery paths with fault injection or deterministic
  fakes before relying on them.

## Ownership

Ownership includes availability, quality degradation, latency, cost anomalies,
fallback behavior, incident response, and review of documented exceptions. An
owner may be a team or service rotation, but not an implicit individual.

## What this principle does not guarantee

- continuous availability of an inherently AI-only feature;
- equivalent semantics across providers or models;
- safety from indiscriminate retries;
- correctness of a syntactically valid fallback;
- that returning HTTP success is better than an explicit service error.

## Review checklist

Use [`code-review/resilience-checklist.md`](../code-review/resilience-checklist.md).
The offline reference implementation is
[`examples/resilience/correct.py`](../examples/resilience/correct.py).

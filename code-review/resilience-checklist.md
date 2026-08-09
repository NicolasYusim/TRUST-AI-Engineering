# R review — Resilience & Ownership

> Every AI dependency has explicit failure semantics, bounded recovery behavior, an observable service objective, and a named owner. The system fails closed or degrades deliberately according to consequence.

**Review question:** How does this component fail or degrade, and who owns the outcome?

## Block approval until

- [ ] Timeout, refusal, invalid output, quota, and dependency outage have explicit
      outcomes.
- [ ] Retries are limited to appropriate failures and bounded by time/attempts.
- [ ] Side-effecting retries are idempotent.
- [ ] Fallback paths are evaluated as distinct product behavior.
- [ ] Stale cache is prohibited where freshness affects correctness or safety.
- [ ] Authorization and consequential-action failures fail closed.
- [ ] SLOs and operational numbers include an evidence basis.
- [ ] Owner, alert destination, and required runbook are declared.
- [ ] Fault-path tests exercise the claimed behavior.

## Evidence expected in the PR

- updated `trust.yaml`;
- deterministic failure/fallback tests;
- dashboard/runbook link where required;
- link to any exception.

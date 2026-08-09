# U review — Utility & Bounds

> Every AI call has an expected user or business benefit and explicit cost, latency, and resource bounds. Choose the lowest-cost path that meets measured quality and safety requirements.

**Review question:** Is this the cheapest and fastest path that meets the required quality and safety?

## Block approval until

- [ ] The product outcome and quality/safety target are explicit.
- [ ] A deterministic or cheaper path was considered where it can meet the target.
- [ ] Input, output, tool-loop, latency, and spend bounds are declared.
- [ ] Routing choices point to evaluation evidence rather than model reputation.
- [ ] Cache keys include tenant, context, locale, policy/freshness, and other
      validity dimensions that apply.
- [ ] Generated output is not cached as authoritative data without validation.
- [ ] Cost and latency are observable by component and route.
- [ ] Operational numbers carry an evidence basis and evidence/source when needed.

## Evidence expected in the PR

- updated `trust.yaml`;
- baseline/candidate measurements or an explicitly illustrative calculation;
- cache invalidation and isolation tests when caching is used;
- link to any exception.

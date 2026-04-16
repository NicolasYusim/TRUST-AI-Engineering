# R — Resilience & Responsibility

> **Axiom:** An AI component is a probabilistic external service. It cannot be a single point of failure. Every degradation must have an owner.

---

## The Problem This Solves

AI APIs fail. They fail due to provider outages, rate limits, network timeouts, context length violations, malformed inputs, and billing issues. When they fail, they fail in ways that are often unpredictable and non-deterministic.

The mistake is treating an AI call like a function call to a local library. It isn't. It's a network call to an external service with:
- No SLA that matches your product's uptime requirements
- Latency that varies by 10-50x depending on load
- Failure modes that change without notice
- Pricing that can spike unexpectedly

**The Resilience principle says:** design as if the AI will fail, because it will.

---

## The Cascade Fallback Pattern

Every AI component should have a documented degradation path:

```
┌─────────────────────────────────────────────────┐
│  Tier 1: Primary AI (best quality)               │
│  → GPT-4o, Claude Opus, Gemini Ultra             │
└────────────────────┬────────────────────────────┘
                     │ on failure / timeout
                     ▼
┌─────────────────────────────────────────────────┐
│  Tier 2: Secondary AI (different provider)       │
│  → Smaller model or competing provider           │
│  → Slower or lower quality, but independent      │
└────────────────────┬────────────────────────────┘
                     │ on failure / timeout
                     ▼
┌─────────────────────────────────────────────────┐
│  Tier 3: Cache                                   │
│  → Last known good response for this input       │
│  → Stale is better than nothing for many cases   │
└────────────────────┬────────────────────────────┘
                     │ on cache miss
                     ▼
┌─────────────────────────────────────────────────┐
│  Tier 4: Deterministic stub                      │
│  → Hardcoded safe response                       │
│  → Routes to human review queue                  │
│  → Does NOT pretend to be an AI response         │
└─────────────────────────────────────────────────┘
```

Not every component needs all four tiers. An internal analytics tool might need only Tier 3 and 4. A customer-facing feature in a medical app needs all four.

**The key rule:** at no tier does the system crash. The degradation is controlled, visible, and logged.

---

## Failure Types and How to Handle Them

| Failure type | Retryable? | Strategy |
|---|---|---|
| `RateLimitError` (429) | Yes, with backoff | Exponential backoff, then fallback |
| `APITimeoutError` | Yes, once | Single retry with shorter timeout, then fallback |
| `ServiceUnavailableError` (503) | Yes, briefly | 1-2 retries, then skip to Tier 2 |
| `InvalidRequestError` (400) | No | Fix the input, log as bug, return stub |
| `AuthenticationError` (401) | No | Alert immediately, return stub |
| `ContextLengthExceeded` | No | Truncate input, retry once, else stub |
| Network timeout (no response) | Yes, once | Retry with shorter timeout, then fallback |

---

## Ownership

An AI component without an owner is an incident waiting for a victim.

**Every AI component should have a documented owner who is responsible for:**
- Availability metric (e.g. success rate > 99%)
- Latency metric (e.g. p95 < 3s)
- Cost metric (e.g. daily spend within budget)
- Fallback activation rate (e.g. < 5% of calls use fallback)
- On-call rotation for incidents

This doesn't require a dedicated team. One engineer can own multiple components. But it must be explicit and documented — not assumed.

---

## Rollout Safety

Model and prompt changes should never go to 100% of traffic immediately.

**Recommended rollout sequence:**

```
1. Shadow mode   → new version runs in parallel, results not used, only logged
2. Canary        → 1-5% of traffic, monitor metrics for 24h
3. Staged rollout → 25% → 50% → 100% with metric gates between steps
4. Full rollout  → revert capability must remain available for 48h
```

A/B testing serves both rollout safety and evaluation: you can directly compare new vs old on production traffic.

---

## Metrics to Monitor

| Metric | Alert threshold | Why |
|---|---|---|
| **AI success rate** | < 99% over 5 min | Primary health signal |
| **Fallback activation rate** | > 5% over 10 min | Provider degradation early warning |
| **p95 latency** | > 8s | UX degradation |
| **Error rate by type** | Rate limit spike | Quota management |
| **Estimated cost per hour** | > 2x baseline | Runaway cost detection |

---

## The "Orphan Component" Anti-Pattern

An orphan AI component is one that:
- Has no named owner
- Has no alerts
- Has no fallback
- Was integrated once and never reviewed again

Orphan components are how AI integrations become production incidents. The pattern is predictable: component works during development, goes to production, AI provider changes something 6 months later, component silently degrades, users complain before engineers notice.

The fix is institutional, not technical: every AI component in production must have an entry in your service registry with an owner, SLO, and runbook.

---

## Further Reading

- [`code-review/resilience-checklist.md`](../code-review/resilience-checklist.md)
- [`examples/resilience/`](../examples/resilience/)

# Code Review Checklist — R: Resilience

> **Axiom:** An AI component is a probabilistic external service. It cannot be a single point of failure. Every degradation must have an owner.
>
> **The eternal question:** *"What does the system do when AI is unavailable? Who is responsible for this?"*

---

## Before Approving a PR, Confirm:

### 1. Failure modes are explicit

- [ ] The AI call is wrapped in error handling — a raw exception from the provider cannot propagate to the user
- [ ] Timeout is configured explicitly (do not rely on provider defaults)
- [ ] Retry logic exists for transient errors (rate limits, 5xx) with **exponential backoff**
- [ ] Non-retryable errors (invalid input, context too long) are handled separately from transient ones

### 2. Fallback strategy is defined

- [ ] There is a documented answer to: *"what happens when this AI call fails?"*
- [ ] At least one of these fallback tiers is implemented:
  - [ ] **Tier 1** — Alternative provider or smaller model
  - [ ] **Tier 2** — Cached response from a previous successful call
  - [ ] **Tier 3** — Deterministic stub / degraded-but-functional response
- [ ] The fallback does **not silently pretend** success — it's distinguishable in logs and, where appropriate, in UX

### 3. Ownership is assigned

- [ ] There is a named owner for the AI component's availability metric
- [ ] Alerting exists (or is planned) for: error rate spike, latency spike, fallback activation rate
- [ ] Runbook or incident response notes exist for: provider outage, unexpected cost spike

### 4. Rollout is controlled

- [ ] Model or prompt changes are not going out to 100% of traffic immediately
- [ ] Shadow mode, canary, or A/B is in place for significant changes

---

## Red Flags to Block a PR

```
❌  response = openai.chat(...)          # no try/except, no timeout
❌  except Exception: pass               # swallowing the error silently
❌  # no fallback path, application returns 500 on AI failure
❌  timeout not set — relies on provider default (often 10 min+)
```

## Green Flags

```
✅  try:
        response = call_primary_ai(prompt, timeout=8)
    except ProviderUnavailable:
        response = call_fallback_ai(prompt, timeout=5)
    except (RateLimitError, TimeoutError):
        response = get_cached_response(prompt_hash) or DEGRADED_STUB
    finally:
        metrics.record(fallback_used=response.is_fallback)

✅  alert if fallback_rate > 5% over 10 min
✅  owner: @engineer-name in service registry
```

---

## The Cascade Pattern

Every resilient AI integration should have a mental model like this:

```
Primary AI (best quality)
    ↓ [on failure/timeout]
Alternative AI or smaller model
    ↓ [on failure/timeout]
Cache (stale is better than nothing)
    ↓ [on cache miss]
Deterministic stub (known-safe response)
    ↓ [if stub is inappropriate for context]
Graceful error with user messaging
```

The system **never crashes** because an AI call failed.

---

## Questions to Ask the Author

1. *"What happens to the user if the AI provider returns a 503 right now?"*
2. *"Who gets paged if this AI component's error rate hits 20%?"*
3. *"Is there a circuit breaker, or will we hammer the provider during an outage?"*

---

→ See [`examples/resilience/`](../examples/resilience/) for violation and correct implementation side-by-side.

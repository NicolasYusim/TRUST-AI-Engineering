# Maturity Levels

> T.R.U.S.T. should not cause overengineering on day one. The framework is introduced as the product matures and the cost of failure increases.

---

## The Core Principle

The right level of rigor is determined by two factors:

1. **Stakes** — what happens when the AI component fails or produces a bad output?
2. **Scale** — how many users and calls are affected?

A bug in an AI feature affects 10 beta users differently than the same bug affecting 10,000 paying customers. The same principle applies to monitoring, fallbacks, and eval infrastructure: the investment should be proportional to the exposure.

---

## Level 1 — MVP

**Context:** Pre-launch, prototype, or internal tool. Few users, high tolerance for imperfection, fast iteration is the priority.

### Required
| Principle | Minimum Implementation |
|---|---|
| **S** | Output is a validated schema, not parsed text. Start with Pydantic or equivalent from day one — it's cheap to add early and expensive to retrofit later. |
| **U** | Set explicit `max_tokens`. Don't call frontier models for tasks a smaller model can handle. |
| **T (Traceability)** | Log prompt version and model version alongside responses. One structured log line per call. |

### Not Yet Required
- Cascade fallbacks (R) — acceptable to have a single API call with basic error handling
- Offline eval pipeline (T Testability) — acceptable to test manually
- Metric ownership (R) — acceptable for one person to watch everything informally
- Semantic caching (U) — acceptable if scale is low

### The MVP Non-Negotiable
The one thing you must never skip, even at MVP: **structured output with validation.**

Retrofitting structured output into a system that was built on text parsing is painful, bug-prone, and requires touching every integration point. It's 30 minutes to add on day one. It's 2 weeks to add in month six.

---

## Level 2 — Product-Market Fit

**Context:** Paying customers, real usage, bugs now have consequences (churn, reputation, support cost).

### Add at This Level
| Principle | What to Add |
|---|---|
| **T (Testability)** | Build a golden dataset of 50–100 examples. Run it before every prompt or model change. Define at least one metric and threshold. |
| **R (full)** | Implement the cascade fallback pattern. At minimum: primary AI → stub. Ideally: primary → secondary → cache → stub. |
| **R — Ownership** | Name a metric owner for each AI component. Define what "degraded" means and who gets paged. |
| **U — Caching** | Add exact-match caching for repeated queries. Semantic caching if there's significant query overlap. |
| **U — Cost tracking** | Log token counts per call. Set up a spend alert. |

### The PMF Trigger
The signal to move from Level 1 to Level 2 is: **the first time a user churns or complains because the AI component gave a bad result.**

At that point, you need to be able to answer: what happened, when did it start, how widespread is it, and how do we prevent it next time? Level 2 gives you the infrastructure to answer these questions.

---

## Level 3 — Enterprise / Scale

**Context:** High volume, regulated domains, SLA commitments, or significant business exposure.

### Add at This Level
| Principle | What to Add |
|---|---|
| **T (Traceability)** | Full RAG citation tracking. Groundedness scoring. Sampled prompt logging with PII scrubbing. |
| **R** | Shadow mode and A/B rollout gates. Formal incident response runbook. SLO defined and monitored. Circuit breaker pattern. |
| **U** | Full model routing logic. Tiered cost accounting by feature/team. Budget alerts with auto-throttling. |
| **T (Testability)** | HITL escalation policy with documented thresholds. Guardrails with measured FPR/FNR. Online metric dashboards. Eval CI gate blocking deploys. |
| **Compliance** | Audit trail for AI decisions. Explainability for regulated domains. Data retention and PII handling policy for AI logs. |

### The Enterprise Non-Negotiable
The one thing you must never skip at enterprise scale: **the eval gate must block deploys.**

If evaluations are optional or advisory, they are eventually skipped under deadline pressure. The value of an eval infrastructure is only realized when it is enforced. Eval in CI that fails the build is the only reliable implementation.

---

## Level Transitions Are Not Dates

Maturity levels are not tied to the age of a product or the size of the team. A new product in a high-stakes domain (medical, financial, legal) should consider Level 2 requirements from the beginning. A long-running internal tool with low stakes may never need Level 3.

The question is always: **what is the cost of failure at this component, and is my current infrastructure proportionate to that cost?**

---

## Quick Reference

```
┌─────────────────────┬──────────────────────────────────────────────────┐
│ Level 1 (MVP)       │ S: schema validation                             │
│                     │ U: max_tokens, model selection                    │
│                     │ T: log model + prompt version                     │
├─────────────────────┼──────────────────────────────────────────────────┤
│ Level 2 (PMF)       │ + T: golden dataset + offline eval               │
│                     │ + R: cascade fallbacks + metric owner             │
│                     │ + U: caching + cost logging                       │
├─────────────────────┼──────────────────────────────────────────────────┤
│ Level 3 (Enterprise)│ + T: HITL + guardrails + eval CI gate            │
│                     │ + R: shadow mode + SLO + runbook                  │
│                     │ + T: RAG citation + groundedness                  │
│                     │ + U: routing + budget alerts                      │
│                     │ + compliance / audit trail                        │
└─────────────────────┴──────────────────────────────────────────────────┘
```

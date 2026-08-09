# T.R.U.S.T. — reference card

Canonical source: [`framework/principles.yaml`](framework/principles.yaml).

## T1 — Traceability & Attribution

> Significant AI results are linked to the versions of their instructions and models, the relevant inputs and sources, and the tool calls that produced them. Traceability supports attribution, audit, and replay; it does not prove truth or guarantee identical reproduction.

**Question:** Can we establish what evidence, configuration, and actions produced this result?

**Code signal:** Immutable references connect the result to input artifacts,
instruction/model versions, retrieved sources, and tool events.

## R — Resilience & Ownership

> Every AI dependency has explicit failure semantics, bounded recovery behavior, an observable service objective, and a named owner. The system fails closed or degrades deliberately according to consequence.

**Question:** How does this component fail or degrade, and who owns the outcome?

**Code signal:** Timeouts, bounded retries, explicit failure modes, telemetry,
and ownership are declared and tested.

## U — Utility & Bounds

> Every AI call has an expected user or business benefit and explicit cost, latency, and resource bounds. Choose the lowest-cost path that meets measured quality and safety requirements.

**Question:** Is this the cheapest and fastest path that meets the required quality and safety?

**Code signal:** Routing, token/output limits, latency SLOs, budgets, and measured
quality gates are visible.

## S — Scope & Structure

> Model output and tool requests are untrusted. Authoritative state, authorization, and side effects remain under a deterministic control plane that enforces schemas, least privilege, and action boundaries before execution.

**Question:** What may the model decide or do, and which code-enforced controls apply before execution?

**Code signal:** Schemas, allowlists, authorization, confirmation, idempotency,
state transitions, and effect limits are enforced before actions execute.

## T2 — Testability & Oversight

> AI changes are evaluated on versioned evidence with metrics and oversight proportional to consequence. Uncertainty is calibrated independently; high-risk actions require abstention, review, or another effective control.

**Question:** What evidence shows this change meets its quality and risk thresholds?

**Code signal:** Versioned suites, predeclared thresholds, regression gates,
calibration evidence, and escalation/abstention paths are tested.

## Mandatory overlay

Apply security, privacy, and compliance controls to all five principles. Risk and
authority determine depth. Product maturity does not waive least privilege,
data protection, or safe action boundaries.

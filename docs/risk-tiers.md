# Risk tiers and authority modes

Controls are selected by consequence and authority. Product stage may influence
implementation capacity, but it does not waive a required control.

The normative machine-readable policy is
[`../policies/risk-tiers.yaml`](../policies/risk-tiers.yaml).

## Consequence tiers

| Tier | Consequence if the component is wrong or unavailable | Typical examples |
|---|---|---|
| `low` | Inconvenience with easy detection and recovery | Draft copy, internal brainstorming |
| `medium` | User harm, material support cost, or business-process disruption | Support answers, document extraction |
| `high` | Significant financial, privacy, access, employment, or operational effect | Account action, fraud routing, production changes |
| `critical` | Safety, rights, or irreversible high-impact effect | Clinical decisions, critical infrastructure action |

Examples are illustrative, not automatic classifications. Classify the concrete
component and deployment context.

The manifest records `consequence_tier` rather than an ambiguous scalar
`risk_tier`. It also requires likelihood, exposure, detectability, a rationale,
reviewer, and review date. These fields make under-classification reviewable;
they do not replace a domain risk assessment.

## Authority modes

| Mode | Maximum model role |
|---|---|
| `advisory` | Produce information or a proposal; no tools |
| `read_only` | Read scoped resources through allowlisted tools |
| `reversible_write` | Propose reversible side effects executed by a control plane |
| `irreversible_action` | Propose consequential or difficult-to-reverse effects |

Authority is determined by effective capability, including transitive tool access,
not by the name of the agent or endpoint.

## Selection rule

Use the higher control requirement indicated by:

- consequence tier;
- authority mode;
- data classification and tenant exposure;
- traffic/exposure and detectability;
- applicable contractual or legal requirements.

A low-consequence component with write authority is not automatically low risk.
The reference policy therefore limits authority modes by tier and imposes
additional controls for writes.

## Required-control progression

All tiers require ownership, data classification, explicit authority, bounded
resources, failure semantics, trace metadata, a component threat model, a
runbook, and a test suite.

Higher tiers add:

- slice metrics and proportional oversight;
- stronger tenant isolation and audit controls;
- executable operational alert signals;
- confirmation, idempotency, and compensation for writes;
- independent approval or effective abstention for critical actions;
- stricter exception approval and expiry.

The machine policy encodes these requirements as control statuses. High-tier
components require source provenance, slice analysis, oversight, sandboxing,
audit, alert signals, and at least one declared slice. Components with tools
must always log tool events. Reversible writes additionally
require confirmation, payload-bound idempotency, and transaction or compensation
evidence. Critical components require strict tenant isolation, independent
approval, at least two slices, and shorter exception lifetimes.

Run `./trust lint` to validate declarations and `./trust verify` to resolve and
execute their evidence.

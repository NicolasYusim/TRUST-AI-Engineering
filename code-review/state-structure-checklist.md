# S review — Scope & Structure

> Model output and tool requests are untrusted. Authoritative state, authorization, and side effects remain under a deterministic control plane that enforces schemas, least privilege, and action boundaries before execution.

**Review question:** What may the model decide or do, and which code-enforced controls apply before execution?

## Block approval until

- [ ] Provider constraints and local schema validation are both used where
      structured output is required.
- [ ] Domain invariants and evidence are checked separately from data types.
- [ ] Authoritative state is stored outside model conversation history.
- [ ] Allowed tools, resources, transitions, and network destinations are explicit.
- [ ] Authorization uses current identity/tenant/resource state, not prompt text.
- [ ] The complete action/plan is validated before side effects execute.
- [ ] Consequential actions define confirmation, idempotency, and
      transaction/compensation behavior.
- [ ] Confirmation is bound to authenticated identity, tenant, and the canonical
      complete action plan rather than represented by a boolean.
- [ ] Idempotency keys are scoped and payload-bound; conflicting reuse fails.
- [ ] Audit events exclude raw arguments/secrets, and alert claims name an
      executable signal rather than treating a test failure as monitoring.
- [ ] Per-tool and total effect/time/step bounds are enforced.
- [ ] Refusal, truncation, invalid output, and unknown state fail explicitly.
- [ ] Injection scanners are treated as signals, not trust boundaries.

## Evidence expected in the PR

- updated `trust.yaml`;
- schema and negative authorization tests;
- side-effect/idempotency tests;
- link to any exception.

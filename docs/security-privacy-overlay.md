# Security, privacy, and compliance overlay

This overlay applies across T1, R, U, S, and T2. It is not deferred until an
enterprise stage.

## Data and privacy

- Classify prompts, retrieved context, outputs, traces, and evaluation data.
- Minimize collection and retention; use approved references instead of raw
  payloads where possible.
- Define whether PII, secrets, regulated data, and cross-border transfer are
  permitted.
- Enforce tenant isolation in retrieval, cache keys, logs, tools, and evaluation.
- Restrict trace/eval access and test deletion and retention behavior.

## Identity and authority

- Authenticate the caller and propagate identity through the control plane.
- Authorize every tool against tenant, resource, action, and current state.
- Expose only the capabilities needed for the current node.
- Bind confirmation to authenticated identity, tenant, and the canonical action
  plan; a generic boolean is not approval.
- Use tenant-scoped, payload-bound idempotency for writes, and reject key reuse
  with a different payload.
- Require a transaction or a tested compensation strategy for reversible writes,
  and independent approval for irreversible actions.

## Untrusted content and prompt injection

User content, retrieved pages, documents, tool results, memory, and cross-agent
messages are untrusted data. Keep them structurally separate from system policy.

Injection scanners, classifiers, delimiters, and string filters may reduce noise
or trigger review. They do not make content trusted. A secure design remains safe
when a scanner misses an attack because the model lacks unauthorized capability
and the control plane validates every proposed action.

## Isolation and supply chain

- Sandbox generated code and untrusted parsers with CPU, memory, time, filesystem,
  and network limits.
- Restrict outbound network destinations and credentials.
- Pin and inventory model adapters, libraries, models, datasets, and indexes.
- Verify artifact integrity and monitor deprecation/security notices.
- Separate development, evaluation, and production credentials and data.

## Operations and assurance

- Threat-model the component and its transitive tools.
- Log authorization decisions and effects without leaking raw tool arguments,
  secrets, or unnecessary personal data.
- Distinguish executable alert signals from test failures; an undeployed
  reference should declare alerts `not_applicable`, not `enforced`.
- Test negative authorization, tenant crossover, injection, duplicate effects,
  rollback, and degraded modes.
- Record legal/compliance assumptions as scoped decisions, not universal claims.
- Give every exception an owner, expiry, compensating control, and approval.

## Relationship to T.R.U.S.T.

| Principle | Overlay focus |
|---|---|
| T1 | privacy-aware provenance, access-controlled audit data |
| R | fail-closed security behavior and incident ownership |
| U | resource-abuse limits and tenant-safe caching |
| S | least privilege, authorization, schemas, safe effects |
| T2 | adversarial tests, oversight evidence, exception review |

# Practices — 2026 Q3

| Field | Value |
|---|---|
| Version | `2026-Q3` |
| Verified | `2026-07-27` |
| Next review | `2026-08-27` |
| Status | Current |

Practices are informative implementation guidance. Durable definitions live in
[`../framework/principles.yaml`](../framework/principles.yaml). Provider/model
facts are kept separately in [`../registry/models.yaml`](../registry/models.yaml)
and must be reverified before adoption.

## T1 — Traceability & Attribution

- Store versioned prompts/policies as artifacts; record content hashes and stable
  artifact references.
- Capture provider request IDs, model/adapter version, observable parameters,
  input/source artifact IDs, tool events, refusal/finish status, and output ID.
- Keep sensitive payloads out of general logs; use an access-controlled artifact
  store with explicit retention.
- For RAG, version corpus, index, chunking policy, filters, and selected chunks.
- For agents, record validated action plans and authorization/effect outcomes,
  not hidden chain-of-thought.

## R — Resilience & Ownership

- Set a component-specific total time budget and bounded retry policy.
- Retry only classified transient failures and use idempotency for effects.
- Evaluate every model/provider fallback on the same blocking contract.
- Prefer explicit unavailable or human-handoff behavior when fallback semantics
  would be unsafe.
- Test timeout, invalid output, refusal, quota, stale cache, and provider outage
  with deterministic fakes.

The reference component timeout in
[`../components/support-answer-generator/trust.yaml`](../components/support-answer-generator/trust.yaml)
is tagged `illustrative`; it is not a universal default.

## U — Utility & Bounds

- Route by a measured quality/safety/latency/cost frontier on your workload.
- Bound input, output, tool steps, effects, and total elapsed time.
- Observe spend and latency by component, route, tenant class, and outcome.
- Cache only validated results whose tenant, policy, locale, freshness, and
  conversational context match.
- Re-run routing evidence after a provider, price, traffic, or task change.

Do not maintain a prose table of supposedly current model prices. Dated primary
facts belong in the registry; deployment-specific selection belongs in evidence.

## S — Scope & Structure

- Prefer provider schema constraints where supported and always validate locally.
- Validate domain invariants and source evidence after structural validation.
- Keep authoritative state and authorization outside provider sessions.
- Compile allowed tools/transitions in code and scope each tool to tenant,
  resource, and action.
- Validate a complete action before execution.
- For writes, use confirmation where required, idempotency keys, per-tool effect
  limits, and real transaction or compensation semantics.
- Treat every user/retrieval/tool/handoff string as untrusted; scanners may add a
  signal but never grant authority.

## T2 — Testability & Oversight

- Version suites and record their population, slices, provenance, and limitations.
- Predeclare blocking metrics and evidence labels.
- Keep development examples separate from held-out evidence.
- Calibrate judge models and uncertainty signals against independent outcomes.
- Use asymmetric metrics where false negatives and false positives have
  different consequences.
- Automate the eval gate required by the component consequence tier and effective
  authority.
- Monitor production outcomes and drift with privacy-aware sampling.

An executable gate declares a shell-free command, suite SHA-256, population,
evaluation date, evidence artifact, comparator, threshold, observed value, unit,
and result key. Run `./trust verify`; file existence alone is not evidence.

## Control status

- `enforced` references implementation, tests, a result artifact, or the required
  operational document.
- `not_applicable` states why the control cannot apply and is rejected when tier
  or authority policy requires it.
- `unsupported` marks an unresolved evidence decision in a generated draft and
  always fails the repository gate.
- `exception` links a schema-valid, independently approved, unexpired record.

Use `./trust lint` for declaration and policy semantics, then `./trust verify`
for hashes, cross-links, observed results, exception validity, and suite
execution.

## Provider/model facts

Run:

```bash
./trust registry lint
```

Registry entries declare source URL, verification date, status, and owner. They
are facts observed on that date, not endorsements or automatic routing choices.

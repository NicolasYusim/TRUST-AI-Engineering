# T1 — Traceability & Attribution

> Significant AI results are linked to the versions of their instructions and models, the relevant inputs and sources, and the tool calls that produced them. Traceability supports attribution, audit, and replay; it does not prove truth or guarantee identical reproduction.

**Review question:** Can we establish what evidence, configuration, and actions produced this result?

## Intent

Traceability makes an AI execution investigable. A useful trace connects an
output to the configuration, evidence, and actions that produced it without
assuming that the model exposes a faithful internal reasoning process.

Keep these properties distinct:

- **Attribution:** identify the inputs, sources, instructions, model, and tools.
- **Auditability:** investigate what the system received, decided, and executed.
- **Replayability:** re-run a captured snapshot when the provider and artifacts
  remain available.
- **Correctness:** determine whether the output is supported and fit for use.

The first three support the fourth; none proves it. A probabilistic or retired
provider model may not reproduce an identical answer.

## Minimum control

For each significant result, retain or reference:

- request/run identifier and timestamp;
- component, prompt/policy, model, and adapter versions;
- immutable input artifact identifiers or privacy-preserving snapshots;
- retrieved source and chunk identifiers, including corpus/index version;
- tool requests, authorization decisions, results, and side effects;
- output artifact, refusal/degradation status, and usage metadata.

References must resolve for the declared retention period. A hash alone proves
integrity only when the corresponding artifact is retained somewhere.

## Privacy boundary

Traceability does not mean indiscriminate logging. Apply data minimization,
redaction, access control, encryption, purpose limitation, and deletion policy.
Store sensitive payloads in an approved artifact store and put opaque references
in operational logs.

Do not record hidden chain-of-thought. Record observable decisions, evidence,
tool events, policy outcomes, and concise system-generated rationales intended
for audit.

## RAG and agentic systems

For retrieval, record query transformations, corpus/index version, source IDs,
scores, filters, and final context selection. For agents, record the validated
plan or action, authorization result, tool arguments after redaction, idempotency
key, effect result, and state transition.

## What this principle does not guarantee

- that a cited source is accurate;
- that the model used the source correctly;
- that a replay produces byte-identical output;
- that storing more data is legally permitted;
- that an explanation generated after the fact reflects internal reasoning.

## Review checklist

Use [`code-review/traceability-checklist.md`](../code-review/traceability-checklist.md).
The offline reference implementation is
[`examples/traceability/correct.py`](../examples/traceability/correct.py).

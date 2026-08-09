# T1 review — Traceability & Attribution

> Significant AI results are linked to the versions of their instructions and models, the relevant inputs and sources, and the tool calls that produced them. Traceability supports attribution, audit, and replay; it does not prove truth or guarantee identical reproduction.

**Review question:** Can we establish what evidence, configuration, and actions produced this result?

## Block approval until

- [ ] A request/run ID links input artifacts, result, and observable actions.
- [ ] Prompt/policy, model, adapter, corpus, and index versions are recorded where
      they affect behavior.
- [ ] Referenced inputs and sources are retained or resolvable for the declared
      audit period.
- [ ] RAG selection and agent tool events are recorded with stable source IDs.
- [ ] Logs distinguish attribution, replayability, and correctness.
- [ ] Sensitive payloads use approved storage, redaction, access, and retention.
- [ ] Hidden chain-of-thought is not requested or stored as an audit mechanism.
- [ ] Trace failure behavior is explicit; audit data is not silently dropped.

## Evidence expected in the PR

- updated `trust.yaml`;
- sample trace or unit test;
- retention/redaction decision;
- link to any exception.

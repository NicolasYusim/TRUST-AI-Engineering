# Scope and structure examples

## Guarantees

- Extraction validates exact fields, types, salary ordering, and source quotes.
- Agent plans are validated completely before the fake store sees a side effect.
- Tool/resource scope, confirmation, per-tool limits, idempotency, and in-memory
  rollback are tested.

## Does not guarantee

- factual correctness of a structurally valid extraction;
- distributed transactionality across real external systems;
- semantic correctness of an allowlisted action;
- security from prompt instructions or injection scanners alone.

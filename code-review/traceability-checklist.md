# Code Review Checklist — T: Traceability

> **Axiom:** AI systems are opaque. An output without a reproducible input chain is unreliable by definition.
>
> **The eternal question:** *"Can I accurately reconstruct why the system gave this answer?"*

---

## Before Approving a PR, Confirm:

### 1. Configuration is versioned and logged

- [ ] The **prompt** (or prompt template) is stored in version control — not hardcoded inline, not in a database field with no history
- [ ] The **model identifier** is logged at the exact patch level (e.g. `gpt-4o-2024-08-06`, not just `gpt-4o`)
- [ ] **Hyperparameters** (temperature, top_p, max_tokens, etc.) are logged per request
- [ ] A **request ID** or correlation ID is generated and propagated through the call

### 2. The result is linked to its inputs

- [ ] The log entry for a response includes: prompt version, model version, hyperparameters, timestamp
- [ ] Given a `request_id`, an engineer can retrieve the exact inputs that produced that output — without guessing
- [ ] If using RAG: the **chunk IDs** retrieved from the knowledge base are logged alongside the response

### 3. RAG-specific (if applicable)

- [ ] Every document chunk fed into context has a tracked source ID
- [ ] The retrieval query is logged separately from the generation prompt
- [ ] Groundedness can be computed post-hoc from logs (which sources actually appeared in the context)

### 4. Observability

- [ ] Logs are structured (JSON or equivalent), not free-form strings
- [ ] A sampling strategy exists — not every call needs full logging, but enough to debug incidents
- [ ] PII/sensitive data is not logged in plaintext

---

## Red Flags to Block a PR

```
❌  model = "gpt-4"           # no version pinning
❌  log.info(f"Response: {response}")  # unstructured, no correlation
❌  # no logging around AI call at all
❌  prompt built from f-string inline, never stored anywhere
```

## Green Flags

```
✅  model = "gpt-4o-2024-08-06"
✅  logger.info({"request_id": req_id, "model": model, "prompt_version": "v2.3.1", ...})
✅  prompt loaded from prompts/summarize_v2.3.1.txt (tracked in Git)
✅  chunk_ids = [c.id for c in retrieved_chunks]  # logged before generation
```

---

## Questions to Ask the Author

1. *"Where can I find the prompt that generated this response in production tomorrow?"*
2. *"If a user reports a wrong answer, can you replay the exact call that produced it?"*
3. *"How do we know which model version is running in prod right now?"*

---

→ See [`examples/traceability/`](../examples/traceability/) for violation and correct implementation side-by-side.

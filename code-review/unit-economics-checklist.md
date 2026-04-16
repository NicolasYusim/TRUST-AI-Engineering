# Code Review Checklist — U: Utility

> **Axiom:** AI computation always consumes resources — computational, time, financial, energetic. An unjustified call is an architectural defect.
>
> **The eternal question:** *"Is this call justified by the complexity of the task?"*

---

## Before Approving a PR, Confirm:

### 1. Model selection is deliberate

- [ ] The model chosen is the **minimum capable** of the task, not the most powerful available
- [ ] A routing decision is documented: *"we use model X for this task because Y"*
- [ ] Classification, routing, and extraction tasks use lighter models than reasoning or generation tasks

### 2. Token usage is controlled

- [ ] Input prompt length is bounded — no unbounded context window stuffing
- [ ] `max_tokens` is set to a value appropriate for the task, not a large default
- [ ] Retrieved documents (RAG) are chunked and filtered before injection — not dumped wholesale
- [ ] The system prompt does not contain redundant or duplicated instructions

### 3. Caching is considered

- [ ] Semantically equivalent requests (same intent, similar phrasing) are handled by cache before hitting the API
- [ ] Deterministic inputs (same exact prompt) use exact-match caching
- [ ] Cache TTL is appropriate for how often the underlying data changes

### 4. Streaming is used where UX demands it

- [ ] Long-form generation uses streaming to reduce perceived latency (TTFT)
- [ ] The UI does not block on full response completion for responses > ~2 seconds

### 5. Cost visibility exists

- [ ] Token count (input + output) is logged per request
- [ ] Cost per call can be computed from logs
- [ ] There is a budget alert or rate limit before costs become catastrophic

---

## Red Flags to Block a PR

```
❌  model = "gpt-4o"   # for a task that's just entity extraction
❌  max_tokens = 4096  # hard default, not thought about
❌  context = "\n".join(ALL_DOCUMENTS)  # dump everything in
❌  # no caching, every user asking the same FAQ hits the API
❌  # no cost logging
```

## Green Flags

```
✅  model = router.select(task_complexity)
    # → "gpt-4o-mini" for classification
    # → "gpt-4o" for multi-step reasoning

✅  context = retriever.top_k(query, k=5, max_chars=3000)

✅  @semantic_cache(ttl=3600)
    def get_answer(query: str) -> str: ...

✅  metrics.record(input_tokens=usage.prompt_tokens,
                   output_tokens=usage.completion_tokens,
                   estimated_cost_usd=compute_cost(usage))
```

---

## The Model Routing Mental Model

```
Task complexity        →  Model tier
─────────────────────────────────────
Binary classification  →  Fine-tuned small / local
Slot filling / extract →  Small frontier (8B–70B)
Summarization          →  Mid-tier
Structured reasoning   →  Mid-to-large frontier
Open-ended generation  →  Large frontier
```

Routing does not have to be automatic. A hardcoded `model = "gpt-4o-mini"` for a classification endpoint *is* routing — deliberate and documented.

---

## Questions to Ask the Author

1. *"Why this model specifically? What would break if we used the next tier down?"*
2. *"What's the estimated monthly cost of this endpoint at 10k requests/day?"*
3. *"What's the p95 response time? Is streaming implemented if it's > 2s?"*

---

→ See [`examples/unit-economics/`](../examples/unit-economics/) for violation and correct implementation side-by-side.

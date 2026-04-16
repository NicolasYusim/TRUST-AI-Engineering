# Code Review Checklist — S: Strict Contracts

> **Axiom:** LLM is a calculator without memory and without the right to orchestrate. The boundary between AI and business logic must be machine-verifiable.
>
> **The eternal question:** *"Can a validator check the output of this AI component without human intervention?"*

---

## Before Approving a PR, Confirm:

### 1. Outputs are structured

- [ ] The AI is asked to return a **defined schema** (JSON, function call, structured output), not free text
- [ ] The schema is defined in code (Pydantic model, JSON Schema, TypeScript type), not in a comment or prose description
- [ ] The schema is validated **before** the result is used in business logic
- [ ] Validation failure triggers an automatic **retry with error feedback** — not a silent fallback or crash

### 2. State lives outside the model

- [ ] Conversation state, session state, and workflow state are stored in code/database — not reconstructed from prompt history
- [ ] The model is not expected to "remember" anything across calls that isn't explicitly passed in
- [ ] Multi-step workflows use an explicit state machine — the model decides within a node, code controls transitions

### 3. Orchestration is strictly bounded

- [ ] The model does not decide *which tool to call next* without code-level validation of that decision
- [ ] Control flow (if/else, loops, sequences) is in code, not in prompt instructions
- [ ] Tool calls / function calls go through a defined interface, not through string parsing of model output

### 4. Retry logic is schema-aware

- [ ] If the model returns an invalid structure, the retry prompt includes the **specific validation error**
- [ ] Maximum retries are bounded (e.g. 3 attempts), after which the call fails explicitly
- [ ] Retry attempts are logged separately (to measure how often the model fails schema compliance)

---

## Red Flags to Block a PR

```
❌  response_text = ai.complete(prompt)
    # then: if "yes" in response_text.lower(): ...
    # → parsing intent from free text

❌  prompt += f"\nPrevious result: {last_result}"
    # → state smuggled through prompt, not stored externally

❌  action = response["next_step"]  # trusting model to pick control flow
    if action == "search": search()
    elif action == "summarize": summarize()
    # → model is orchestrating, code is just executing blindly

❌  # schema defined only in prompt: "respond with JSON like: {name: ..., age: ...}"
    # no validation, no schema object in code
```

## Green Flags

```
✅  class SummaryOutput(BaseModel):
        title: str
        key_points: list[str]
        confidence: float = Field(ge=0.0, le=1.0)

    result = ai.complete_structured(prompt, schema=SummaryOutput)
    # pydantic validates, raises ValidationError on bad output

✅  # Retry with error context
    for attempt in range(MAX_RETRIES):
        try:
            return SummaryOutput.model_validate_json(raw)
        except ValidationError as e:
            prompt = add_error_context(prompt, str(e))
    raise MaxRetriesExceeded()

✅  # State machine — model only decides within a node
    state = WorkflowState.load(session_id)
    decision = model.decide(state.current_node_context())
    state.transition(decision)   # code validates transition is legal
    state.save(session_id)
```

---

## The Key Insight

The model's output is **untrusted input** — treat it exactly like user input from the internet. You wouldn't apply business logic directly to an unvalidated HTTP request body. Don't apply it to unvalidated model output either.

---

## Questions to Ask the Author

1. *"Where is the schema for this model's output defined in code?"*
2. *"What happens if the model returns `null` for a required field?"*
3. *"Is there any place where we parse the model's text to infer its intent?"*

---

→ See [`examples/state-structure/`](../examples/state-structure/) for violation and correct implementation side-by-side.

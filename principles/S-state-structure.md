# S — State & Structure

> **Axiom:** LLM is a stateless executor. It may orchestrate only within the boundaries of a verifiable sandbox contract — where permitted tools, state transitions, and output shapes are declared in code and enforced before execution. The boundary between AI and business logic must be machine-verifiable.

---

## The Problem This Solves

There is a tempting architectural pattern when integrating LLMs: let the model handle everything. Give it a long system prompt, pass in the conversation history, let it decide what to do next. It feels elegant — one API call, everything handled.

This pattern fails in production for several reasons:

1. **The model has no memory.** Each call is stateless. "Memory" reconstructed from prompt history is fragile, expensive, and grows unboundedly.
2. **Uncontrolled orchestration breaks auditability.** If the model freely decides what tool to call next, you lose control over the execution graph. You cannot test it, you cannot audit it, you cannot make it deterministic. *Bounded* orchestration — within a machine-verifiable sandbox contract — is a different matter and is explicitly supported by this principle.
3. **Unstructured output breaks everything downstream.** Business logic applied to free text is a maintenance nightmare. The model "meant" to say yes but wrote "Sure, I can do that" — your parser breaks.

**The State & Structure principle says:** LLM is a *stateless executor*. It receives a well-defined input, produces a well-defined output, and code handles everything else. When the model orchestrates, it does so only within the boundaries of a sandbox contract it cannot modify.

---

## Structured Output: The Core Practice

The model's output should be validated the same way you validate HTTP request bodies from untrusted users — because that's exactly what it is: untrusted input.

### The schema-first workflow:

```
1. Define output schema in code (Pydantic, TypeScript, JSON Schema)
2. Pass schema to model (function calling, JSON mode, structured outputs)
3. Validate model output against schema
4. On validation failure: retry with error context (max 3 times)
5. On max retries: raise explicitly — never silently degrade
```

### Why retry with error context?

When the model returns an invalid structure, it usually made a small, correctable mistake (wrong type, missing field). Telling it exactly what went wrong in the retry prompt fixes ~85% of validation failures on the first retry.

```python
# ✅ Retry with specific error feedback
retry_prompt = f"""Your previous response failed validation:
Error: {validation_error}
Please correct your response and return only valid JSON."""
```

---

## State Management: Keep It Outside the Model

### What "state outside the model" means

The model does not remember anything between calls. If your workflow needs to:
- Track what step the user is on
- Remember what was decided in a previous turn
- Carry context from call to call

...then *your code* must store and pass that state explicitly. The model receives state as input; it does not maintain state.

**Wrong:**
```python
# Reconstructing state from prompt history
messages.append({"role": "user", "content": user_input})
response = ai.chat(messages)  # model infers state from conversation
messages.append({"role": "assistant", "content": response})
# state = length of messages list
```

**Right:**
```python
# Explicit state object, stored in your database
state = WorkflowState.load(session_id)
prompt = build_prompt(state.current_step, state.collected_data, user_input)
response = ai.complete_structured(prompt, schema=StepOutput)
state.apply(response)
state.save(session_id)
```

---

## Agentic Sandboxing: Orchestration Within Verifiable Contracts

In agentic workflows where the model calls tools, picks next steps, or drives multi-turn chains, the temptation is to let the model "navigate" the workflow through unconstrained reasoning. The failure mode is not orchestration itself — it is *unverifiable* orchestration.

**Agentic Sandboxing** is the pattern that permits model-driven orchestration while keeping it fully auditable and testable: the model may decide what to do next, but only from a set of options that code declares, validates, and enforces.

### What a Sandbox Contract Defines

A sandbox contract is a machine-readable declaration attached to each node or phase of an agentic workflow. It specifies four things:

| Contract dimension | What it constrains |
|---|---|
| **Allowed tools** | Exhaustive list of tools the model may invoke at this node |
| **Allowed transitions** | Set of valid next states reachable from this node |
| **Output schema** | Validated Pydantic / JSON Schema the model's decision must conform to |
| **Effect budget** | Maximum number of external side effects permitted per invocation |

The contract is authored in code, not in a system prompt. The model cannot modify it, extend it, or reason its way around it.

### The Sandbox Pattern

```
1. Code loads the contract for the current node
2. Code exposes ONLY the tools declared in the contract to the model
3. Model produces a structured decision (next action + parameters)
4. Code validates the decision against the contract's output schema
5. Code checks the transition is in the allowed set
6. Code checks the effect budget has not been exceeded
7. Code executes the transition — never the model
```

```python
# ✅ Agentic Sandboxing in practice

@dataclass
class SandboxContract:
    allowed_tools: list[str]
    allowed_transitions: list[str]
    output_schema: type[BaseModel]
    max_effects: int = 1

CONTRACTS: dict[str, SandboxContract] = {
    "classify": SandboxContract(
        allowed_tools=["search_kb", "get_category_list"],
        allowed_transitions=["enrich", "escalate"],
        output_schema=ClassifyDecision,
    ),
    "enrich": SandboxContract(
        allowed_tools=["fetch_entity", "resolve_alias"],
        allowed_transitions=["respond", "escalate"],
        output_schema=EnrichDecision,
        max_effects=2,
    ),
}

def run_node(node: str, context: WorkflowContext) -> WorkflowContext:
    contract = CONTRACTS[node]
    # Only expose tools the contract permits
    tools = tool_registry.subset(contract.allowed_tools)
    raw = model.complete_structured(
        prompt=build_prompt(context),
        tools=tools,
        schema=contract.output_schema,
    )
    decision = contract.output_schema.model_validate(raw)   # schema check
    assert decision.next_state in contract.allowed_transitions  # transition check
    assert count_effects(decision) <= contract.max_effects      # budget check
    return context.apply(decision)
```

### What Remains Prohibited

Agentic Sandboxing permits orchestration; it does not permit free orchestration. The following patterns are still invalid:

- **Dynamic tool discovery** — the model proposes a tool not in the current contract
- **Self-extending contracts** — the model outputs instructions that modify its own allowed set
- **Prompt-only constraints** — "only call tool X" written in the system prompt but not enforced in code
- **Unbounded loops** — agentic chains without a code-enforced step limit or effect budget

### Verifiability Checklist

Before shipping an agentic node, verify:

```
[ ] Every tool available to the model is listed in the contract
[ ] Every possible next state is listed in the contract
[ ] The model's output is validated against a schema before any transition executes
[ ] Effect budget is enforced in code, not trusted from model output
[ ] Contract is unit-testable independent of the model (mock the model, assert contract behaviour)
```

### Architecture Diagram

```
┌──────────────────────────────────────────────────────┐
│                  Sandbox Contract                     │
│  allowed_tools: [search_kb, get_category_list]       │
│  allowed_transitions: [enrich, escalate]             │
│  output_schema: ClassifyDecision                     │
│  max_effects: 1                                      │
└────────────────────┬─────────────────────────────────┘
                     │ code enforces
          ┌──────────▼──────────┐
          │      Node A         │  ← model decides WITHIN contract
          │  (code + model)     │    (next_state, tool_calls, params)
          └──────────┬──────────┘
                     │
        code validates: schema ✓ | transition legal ✓ | budget ✓
                     │
          ┌──────────▼──────────┐     ┌──────────────────────┐
          │      Node B         │     │      Escalate        │
          │      (code)         │     │      (code)          │
          └─────────────────────┘     └──────────────────────┘
```

The model never reaches a node that is not in its current contract's `allowed_transitions`. Code is the authority on control flow; the sandbox contract is the authority on what the model is allowed to decide.

---

## The "Treat Model Output as Untrusted Input" Principle

This is the mental model that unifies everything in this principle:

```
HTTP request body from user  →  validate with schema  →  business logic
Model response               →  validate with schema  →  business logic
```

In both cases, the input is untrusted. In both cases, validation is non-optional. In both cases, validation failure is handled explicitly — not silently swallowed.

If you already have input validation discipline in your codebase, applying it to model outputs is not a new skill. It's the same skill in a new place.

---

## Schema Design Tips

**Be explicit about optionality.** Fields that might not always be present should be `Optional` with a default. Never rely on the model to always provide every field.

**Validate semantic constraints, not just types.** `confidence: float` doesn't tell the model the range is 0.0–1.0. Use `Field(ge=0.0, le=1.0)`.

**Add field descriptions.** Schema descriptions are effectively part of your prompt. Clear field descriptions reduce validation failures.


---

## Further Reading

- [`code-review/state-structure-checklist.md`](../code-review/state-structure-checklist.md)
- [`examples/state-structure/`](../examples/state-structure/)

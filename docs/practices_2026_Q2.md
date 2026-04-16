# Practices — 2026 Q2

---

| | |
|---|---|
| **Version** | 2026-Q2 |
| **Review date** | 2026-Q4 |
| **Status** | Current |

---

> This document contains current tool and implementation recommendations. Unlike the axioms in *principles/*, this document will be updated. Check the version and review date before following recommendations in a new project.

---

## T — Traceability: Current Tools

### Prompt versioning

- Store prompts as plain text files in `prompts/` directory, named with version: `summarize_v2.1.0.txt`
- Alternative: use LangSmith or Weights & Biases for managed prompt tracking
- Do not use database fields with no history for prompt storage

### Structured logging

- **Python:** `structlog` with JSON renderer
- **Node.js:** `pino`
- **Log destination:** any structured log platform (Datadog, Grafana Loki, CloudWatch Logs)

### RAG observability

- **RAGAS** for groundedness and context relevance scoring
- **TruLens** for RAG evaluation pipelines

### Model version aliases → pinned versions (as of Q2 2026)

| **Alias** | **Pin to** | **Notes** |
|---|---|---|
| `gpt-4o` | `gpt-4o-2025-03-26` | Latest stable GA snapshot — verify at OpenAI |
| `gpt-4o-mini` | `gpt-4o-mini-2024-07-18` | Verify for updates at OpenAI |
| `o3` | `o3-2025-04-16` | Reasoning model — requires `reasoning_effort` budget |
| `claude-sonnet` | `claude-sonnet-4-6` | Current recommended Sonnet |
| `claude-opus` | `claude-opus-4-5` | Reasoning model — requires `budget_tokens` parameter |
| `claude-haiku` | `claude-haiku-4-5-20251001` | Current recommended Haiku — verify at Anthropic |
| `gemini-1.5-pro` | Check Google's versioned endpoint | No stable alias — verify each deploy |

*Pin to the most recent stable snapshot. Update deliberately, not automatically.*

---

## R — Resilience: Current Tools

### HTTP client configuration

- Always set explicit timeouts (recommended: **8s** for primary, **5s** for secondary)
- **Python:** `httpx` over `requests` — better async support and timeout handling
- Use `tenacity` for retry logic with exponential backoff
- For reasoning models: extend primary timeout to **120s** — internal reasoning loops can consume significant wall time before the first output token

### Circuit breaker

- **Python:** `pybreaker`
- **Node.js:** `opossum`

### Monitoring and alerting

- **Prometheus + Grafana** for self-hosted
- **Datadog** for managed
- Key metric to alert on: `fallback_activation_rate > 0.05` over 10 minutes

### Semantic caching

**Required approach: context-keyed caching**

A cache key for a conversational system must encode the query *and* its dialogue context. The composite key should include:

- Current user query (embedded)
- Digest of the last N conversation turns (recommended N = 3–5)
- Session topic marker — a short hash derived from the session's canonical topic, if tracked

```python
import hashlib
from dataclasses import dataclass

@dataclass
class SessionContext:
    session_id: str
    recent_turns: list[str]   # last N user+assistant messages
    topic_hash: str           # optional canonical topic identifier

def build_cache_key(query: str, ctx: SessionContext) -> str:
    """
    Produces a composite key that combines the current query
    with a digest of recent conversation turns.
    """
    turn_digest = hashlib.sha256(
        "||".join(ctx.recent_turns).encode()
    ).hexdigest()[:16]
    return f"{ctx.session_id}:{turn_digest}:{query}"
```

Then embed `query + " [context] " + " | ".join(ctx.recent_turns)` jointly for the vector similarity lookup — not the query alone.

**Recommended libraries and patterns:**

- **`semantic-router`** — extend with a `SessionContext` layer to pass joint query+context embeddings; supports pluggable vector backends
- **Redis + pgvector** (self-hosted) — store entries with a `session_context_hash` column; include the hash in the lookup WHERE clause so cross-context hits are structurally impossible
- **LangGraph** — implement a `CacheNode` that receives the full `ConversationState` and derives the composite key before any vector lookup
- **GPTCache** — usable for single-turn or stateless pipelines only; do not use in multi-turn agents without a custom `CacheConfig` that overrides the default key function

**When context drift is detected** (e.g. topic shift detected by a classifier or explicit user signal), invalidate the session's cache partition immediately rather than waiting for TTL expiry.

**Similarity threshold:** **0.92 cosine** remains the recommended lower bound, but this threshold applies to the composite (query + context) embedding, not to the query alone. A match on the bare query below 0.95 that is not reinforced by context agreement should be treated as a miss.

---

## U — Unit Economics: Current Tool Recommendations

### Model routing (as of Q2 2026)

| **Task** | **Recommended model** | **Approx. cost / 1M tokens (Q2 2026)** |
|---|---|---|
| Binary classification | Local Llama 3.3 70B, Qwen 2.5 72B, or `gpt-4o-mini` | Local: infra only (~$0.02–0.05 cloud GPU); API: ~$0.07–0.15 input |
| Extraction (5–10 fields) | Local 70B or `gpt-4o-mini` | Local: infra only; API: ~$0.07–0.15 input |
| Summarization | Local 70B, `claude-haiku`, or `gpt-4o-mini` | Local: infra only; API: ~$0.07–0.25 input |
| Complex reasoning (non-thinking) | `gpt-4o` or `claude-sonnet` | ~$1.00–$1.50 input / ~$4.00–$7.50 output |
| Complex reasoning (thinking) | `o3` (`reasoning_effort="high"`) or `claude-opus` (`budget_tokens`) | Base ~$1.50–$2.00 input + reasoning token surcharge — see below |
| Long-form generation | `gpt-4o` or `claude-sonnet` | ~$1.00–$1.50 input / ~$4.00–$7.50 output |

> ⚠ **Pricing changes frequently:** Verify current pricing at provider sites before production planning. Values above are approximations for planning purposes only.

*Local 70B models (Llama 3.3, Mistral, Qwen 2.5) are the default choice for classification and extraction. Benchmark on your own data and measure infra cost (GPU hours) against hosted API cost before assuming local is cheaper at low request volumes.*

### Reasoning model budget management

**Anthropic Extended Thinking (Python):**

```python
import anthropic

client = anthropic.Anthropic()

# Standard call with explicit budget
response = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=8000,         # output tokens — set separately from thinking budget
    thinking={
        "type": "enabled",
        "budget_tokens": 10000   # reasoning tokens; max 100 000
    },
    messages=[{"role": "user", "content": prompt}]
)

# Separate thinking blocks from answer blocks
for block in response.content:
    if block.type == "thinking":
        internal_reasoning = block.thinking   # log, do not return to user
    elif block.type == "text":
        final_answer = block.text
```

**Anthropic streaming — avoid blank-screen TTFT:**

Without streaming, the model emits nothing until all reasoning is complete, causing a blank screen that can last tens of seconds. Stream thinking blocks separately to give users immediate feedback:

```python
with client.messages.stream(
    model="claude-opus-4-5",
    max_tokens=8000,
    thinking={"type": "enabled", "budget_tokens": 10000},
    messages=[{"role": "user", "content": prompt}]
) as stream:
    for event in stream:
        if event.type == "content_block_start":
            if event.content_block.type == "thinking":
                yield {"type": "thinking_start"}  # show "Thinking…" indicator to user
        elif event.type == "content_block_delta":
            if event.delta.type == "thinking_delta":
                pass  # optionally stream thinking text to a debug panel
            elif event.delta.type == "text_delta":
                yield {"type": "text", "chunk": event.delta.text}  # stream answer
        elif event.type == "content_block_stop":
            if hasattr(event, "content_block") and event.content_block.type == "thinking":
                yield {"type": "thinking_end"}
```

**OpenAI o3 (Python):**

```python
from openai import OpenAI

client = OpenAI()

response = client.chat.completions.create(
    model="o3-2025-04-16",
    reasoning_effort="medium",   # "low" | "medium" | "high"
    # "high" can use up to 100 000 reasoning tokens — use only for genuinely hard tasks
    messages=[{"role": "user", "content": prompt}]
)
answer = response.choices[0].message.content
```

**Budget sizing guidance:**

| **Task complexity** | **Anthropic `budget_tokens`** | **OpenAI `reasoning_effort`** |
|---|---|---|
| Simple multi-step (3–5 steps) | 2 000–5 000 | `low` |
| Moderate reasoning (analysis, planning) | 5 000–15 000 | `medium` |
| Hard reasoning (proofs, complex debugging) | 15 000–50 000 | `high` |
| Maximum (research-grade) | up to 100 000 | `high` |

*Never set `budget_tokens` to its maximum by default. Start at the minimum that meets quality thresholds and increase deliberately.*

### Embedding models

- **`text-embedding-3-small`** — best cost/performance for most retrieval tasks (OpenAI)
- **`text-embedding-3-large`** — use only when small measurably underperforms on your data

### Streaming

- Use streaming for any endpoint where generation time > 2 seconds
- **OpenAI Python:** `stream=True` with `for chunk in response:`
- **Anthropic Python:** `.stream()` context manager
- **Reasoning models:** streaming is mandatory, not optional — see Reasoning model budget management above

### Voice-to-Voice Realtime Models

**Pricing model:**

| Component | Driver | Approx. cost (Q2 2026) |
|---|---|---|
| Audio input (user speech) | Seconds of audio received | ~$0.06 / min |
| Audio output (model speech) | Seconds of audio generated | ~$0.24 / min |
| Text input tokens (system prompt, context) | Tokens | ~$5.00 / 1M |
| Text output tokens | Tokens | ~$20.00 / 1M |

> ⚠ Verify current pricing at provider sites. Output audio is typically **4× more expensive than input** — this asymmetry dominates cost.

**Example calculation — voice support agent:**

```
Assumptions:
  Average call duration:       4 minutes
  Audio input:                 2.5 min (user speaks ~60% of call)
  Audio output:                1.5 min (model responds ~40%)
  System prompt (per session): 800 tokens (injected once per connection)
  Daily call volume:           5 000 calls

Per-call cost:
  Input audio:   2.5 min × $0.06 / min            = $0.150
  Output audio:  1.5 min × $0.24 / min            = $0.360
  System prompt: 800 tokens × $5.00 / 1 000 000   = $0.004
  ─────────────────────────────────────────────────────────
  Total per call:                                    $0.514

Monthly cost (30 days):
  5 000 calls/day × $0.514 × 30 days = $77 100 / month
```

**The silence trap:** Unlike text APIs, an open V2V connection bills for every millisecond — including pauses, hold music, and dead air. A 4-minute call where the user is on hold for 2 minutes still accrues 4 minutes of billing.

**Cost levers specific to V2V:**

| Lever | What it does | Expected impact |
|---|---|---|
| Server-side VAD | Detect end-of-turn server-side; do not send silence windows to the model | Reduces billed input audio by 20–40% |
| Disconnect on inactivity | Close the WebSocket if no speech is detected for N seconds; reconnect on user input | Eliminates idle-connection billing |
| Turn mode vs. continuous mode | Use push-to-talk or server-VAD turn mode instead of a permanently open mic | Prevents runaway billing during user AFK |
| Hard session duration cap | Enforce a maximum session length (e.g. 10 min) server-side | Bounds per-call cost; kills stuck-session runaway |
| Context injection once per connection | Inject system prompt and context at session start, not per turn | Eliminates repeated text-token overhead on long calls |
| `max_response_output_tokens` | Bound model response length explicitly | Direct reduction of the 4× output audio multiplier |

**Cost estimate helper:**

```python
from dataclasses import dataclass

@dataclass
class V2VCallParams:
    call_duration_sec: float
    user_speech_ratio: float       # 0.0–1.0, fraction of call the user speaks
    model_speech_ratio: float      # 0.0–1.0, fraction of call the model speaks
    system_prompt_tokens: int = 800
    daily_call_volume: int = 1

# Q2 2026 approximate rates — verify at provider before use
AUDIO_INPUT_PER_MIN_USD  = 0.06
AUDIO_OUTPUT_PER_MIN_USD = 0.24
TEXT_INPUT_PER_1M_USD    = 5.00

def estimate_v2v_cost(params: V2VCallParams) -> dict:
    """Returns per-call and projected monthly cost for a V2V realtime session."""
    duration_min = params.call_duration_sec / 60.0
    audio_in  = duration_min * params.user_speech_ratio  * AUDIO_INPUT_PER_MIN_USD
    audio_out = duration_min * params.model_speech_ratio * AUDIO_OUTPUT_PER_MIN_USD
    text_in   = params.system_prompt_tokens / 1_000_000  * TEXT_INPUT_PER_1M_USD
    per_call  = audio_in + audio_out + text_in

    return {
        "per_call_usd":           round(per_call, 4),
        "daily_usd":              round(per_call * params.daily_call_volume, 2),
        "monthly_usd_30d":        round(per_call * params.daily_call_volume * 30, 2),
        "audio_input_share_pct":  round(audio_in  / per_call * 100, 1),
        "audio_output_share_pct": round(audio_out / per_call * 100, 1),
    }

# Example — 5 000 calls/day, 4-minute average call
params = V2VCallParams(
    call_duration_sec=240,
    user_speech_ratio=0.625,   # 2.5 min user / 4 min total
    model_speech_ratio=0.375,  # 1.5 min model / 4 min total
    system_prompt_tokens=800,
    daily_call_volume=5_000,
)
print(estimate_v2v_cost(params))
# {'per_call_usd': 0.514, 'daily_usd': 2570.0, 'monthly_usd_30d': 77100.0,
#  'audio_input_share_pct': 29.2, 'audio_output_share_pct': 70.0}
```

**Extend the Business Math checklist with two V2V-specific questions:**

10. **What is the expected average session duration (including silence)?** — not just speech duration; silence is billed at the same rate
11. **Is there a session duration cap and inactivity disconnect enforced server-side?** — without both, a single stuck session can run for hours at full billing rate

---

## S — State & Structure: Current Tools

### Schema validation

- **Python:** Pydantic v2 — the standard
- **TypeScript:** Zod
- **OpenAI structured outputs:** pass `response_format={"type": "json_object"}` or use `parse()` with a Pydantic model
- Always validate tool call arguments with a strict Pydantic model before executing — treat them as untrusted input (see Agentic security below)

### Agent frameworks with external state management

- **LangGraph** — explicit state machine graph, recommended; see Agentic sandboxing below for required safety extensions
- **Temporal** — for long-running, durable workflows where state must survive restarts
- **Avoid:** frameworks that hide the state machine and let the model navigate implicitly

### Agentic sandboxing

**Dimension 1 — Allowed tools**

Declare the permitted tool set per node at graph compile time. Do not allow the model to call tools that are not in the node's declared whitelist:

```python
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

# Only bind tools explicitly approved for this node
search_node = ToolNode(tools=[web_search])       # read-only tools
write_node  = ToolNode(tools=[write_to_db])      # write tools — separate node, separate guard
```

**Dimension 2 — Allowed transitions**

At graph compile time, only add edges between nodes that represent valid transitions in your domain logic. Never add a catch-all edge that allows the model to route itself to any node:

```python
graph = StateGraph(AgentState)
graph.add_node("search", search_node)
graph.add_node("write", write_node)
graph.add_node("end", end_node)

# Only these transitions are permitted — no dynamic edge resolution
graph.add_conditional_edges("search", route_after_search, {"write": "write", "end": "end"})
# "write" can only go to "end" — it cannot loop back to "search"
graph.add_edge("write", "end")
```

**Dimension 3 — Output schemas**

Each node's output must pass a Pydantic schema check before it is injected into the next node's state. Do not pass raw `dict` between nodes:

```python
from pydantic import BaseModel

class SearchOutput(BaseModel):
    results: list[str]
    source_urls: list[str]

def search_node(state: AgentState) -> AgentState:
    raw = call_search_tool(state["query"])
    validated = SearchOutput.model_validate(raw)   # raises ValidationError if malformed
    return {**state, "search_results": validated.results}
```

**Dimension 4 — Effect budget**

An effect budget caps the total number of write or external side-effect operations the agent may perform in a single session. It prevents unbounded execution and self-expanding tool use. Initialize per session; decrement on every side-effectful operation; halt the graph when the budget reaches zero:

```python
from typing import TypedDict

class AgentState(TypedDict):
    messages: list
    effect_budget: int        # set at session start, e.g. 5
    effects_used: list[str]   # audit trail of consumed effects

def write_node(state: AgentState) -> AgentState:
    if state["effect_budget"] <= 0:
        # Do not raise silently — surface the budget exhaustion explicitly
        return {
            **state,
            "messages": state["messages"] + [{
                "role": "system",
                "content": "Effect budget exhausted. No further write operations permitted."
            }]
        }
    result = write_to_db(state["payload"])
    return {
        **state,
        "effect_budget": state["effect_budget"] - 1,
        "effects_used": state["effects_used"] + [f"write_to_db:{result.id}"]
    }

# Initialize per session — do not share budget across sessions
initial_state = AgentState(
    messages=[],
    effect_budget=5,
    effects_used=[]
)
```

*Effect budget should be domain-calibrated. A research assistant reading documents may warrant a budget of 0 (read-only). A workflow agent that writes records may warrant 5–10. No agent should have an unbounded effect budget.*

**Preventing self-expanding contracts**

A self-expanding contract occurs when the agent dynamically registers new tools or rewrites its own node graph at runtime. Prevent this by:

- Compiling the graph with `.compile()` before any messages are processed — LangGraph graphs are immutable after compilation
- Disallowing tool-calling nodes from accepting tool definitions as input (validate that tool call arguments do not contain keys like `function`, `tools`, `schema`, or `instructions`)
- Auditing the `effects_used` list at the end of each session and alerting if the number of unique tool types exceeds the expected set

### Function calling

- **OpenAI:** native function calling / tools
- **Anthropic:** native tool use
- Always validate tool call arguments before executing — treat them as untrusted input

### Agentic security

**Recommended injection defence libraries (H1 2026):**

- **`llm-guard`** — open-source input/output scanning library with a dedicated `PromptInjectionScanner` and `BanSubstrings` scanner; supports both synchronous and async pipelines; self-hosted
  ```python
  from llm_guard.input_scanners import PromptInjection
  from llm_guard import scan_prompt

  scanner = PromptInjection(threshold=0.92)
  sanitised_prompt, results_valid, results_score = scan_prompt(
      [scanner], retrieved_tool_output
  )
  if not all(results_valid.values()):
      raise ValueError("Injection pattern detected in tool output — discarded")
  ```
- **`rebuff`** — purpose-built prompt injection detection; offers a self-hosted API and a managed endpoint; uses a two-layer detector (heuristic + LLM-based)
- **NVIDIA NeMo Guardrails** — now includes an agentic injection rail (`AgentInjectionRail`) specifically designed to intercept tool call arguments before execution

**Required sanitisation pipeline for untrusted input:**

Apply this pipeline to *every* piece of content retrieved from an external source before it is appended to a prompt or passed as a tool argument:

```
[External source output]
       │
       ▼
[1. Structural schema validation — Pydantic]
       │
       ▼
[2. Injection scan — llm-guard PromptInjectionScanner or rebuff]
       │
       ▼
[3. Strip / escape instruction-like strings — remove "ignore previous", "system:", etc.]
       │
       ▼
[4. Optional: secondary LLM-based validation on high-risk content]
       │
       ▼
[Safe to include in prompt or tool argument]
```

**All Q4 2025 mitigations remain in force:**

- Treat all tool call arguments as untrusted input — validate against a strict schema before execution
- Never pass raw tool output back into a prompt without sanitisation — strip or escape instruction-like strings
- Apply Guardrails AI or LlamaGuard as the output guardrail layer in addition to the injection-specific input scanner
- Use a separate, low-capability model for tool argument validation — do not let the same model that calls tools also decide whether to trust its own outputs
- Log all tool calls with arguments and results to your structured log platform for audit and anomaly detection
- For high-risk actions (write, delete, external API calls), require a confirmation step before execution

> ⚠ **Indirect prompt injection:** If your agent retrieves content from the web, databases, or user-uploaded documents, that content can contain adversarial instructions. Treat retrieved context as an untrusted third party — not as part of your system prompt — and run it through the full sanitisation pipeline above before use.

### Cross-agent state handoff

**Core principle: project, don't forward**

The sending agent is responsible for projecting its state into the smallest typed envelope that satisfies the receiver's needs. The receiving agent is responsible for validating that envelope independently — it must never assume the shape of the incoming object is correct.

**Step 1 — Define a typed transfer envelope per handoff pair**

Each handoff has its own Pydantic model. Do not reuse a generic `dict` or a full agent state type:

```python
from pydantic import BaseModel, field_validator
from uuid import UUID
from datetime import datetime

class ClassifierToBillingEnvelope(BaseModel):
    """
    Only the fields billing needs — nothing else leaves the classifier.
    """
    session_id: UUID
    user_id: str
    classification_label: str          # e.g. "subscription_upgrade"
    classification_confidence: float   # 0.0–1.0
    requested_plan: str
    handoff_timestamp: datetime

    @field_validator("classification_confidence")
    @classmethod
    def confidence_in_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        return v
```

**What must never appear in a transfer envelope:**

| **Field type** | **Why excluded** |
|---|---|
| System prompt or any fragment of it | The receiving agent must not see the sender's instructions — leakage enables prompt injection through state |
| Raw tool output | May contain adversarial content; the sender must sanitise before including any derived field |
| Internal reasoning trace | Exposes internal chain-of-thought; may include sensitive intermediate data |
| Full message history | Usually unnecessary; include only a session reference ID |
| Debug / diagnostic fields | Strip all fields prefixed with `_debug`, `_trace`, `_raw` |

**Step 2 — Produce the envelope in a dedicated projection function**

```python
from uuid import UUID
from datetime import datetime, timezone

def project_to_billing(state: ClassifierAgentState) -> ClassifierToBillingEnvelope:
    """
    Explicit projection — only named fields are forwarded.
    Any new field added to ClassifierAgentState is NOT automatically forwarded.
    """
    return ClassifierToBillingEnvelope(
        session_id=state.session_id,
        user_id=state.user_id,
        classification_label=state.top_label,
        classification_confidence=state.top_score,
        requested_plan=state.extracted_plan,
        handoff_timestamp=datetime.now(timezone.utc),
    )
```

Never use `state.dict()` or `**state.__dict__` to populate the envelope — this silently forwards every field, including fields that should not cross the boundary.

**Step 3 — Validate on receipt**

The receiving agent must validate the envelope against its own schema before using any field. Do not trust that the sender correctly populated all fields:

```python
def billing_agent_entry(raw_handoff: dict) -> BillingAgentState:
    try:
        envelope = ClassifierToBillingEnvelope.model_validate(raw_handoff)
    except ValidationError as exc:
        # Log the failure with the session reference — do not log raw_handoff (may contain PII)
        logger.error("invalid_handoff_envelope", session_id=raw_handoff.get("session_id"), error=str(exc))
        raise

    # Text fields sourced from user input must be scanned before any prompt inclusion
    safe_label = scan_for_injection(envelope.classification_label)
    ...
```

**Step 4 — Scan text fields for injection before prompt inclusion**

Any string field in the envelope that originates (directly or indirectly) from user input must pass through the injection scan pipeline (see Agentic security above) before the receiving agent includes it in a prompt or tool argument:

```python
from llm_guard.input_scanners import PromptInjection
from llm_guard import scan_prompt

_injection_scanner = PromptInjection(threshold=0.92)

def scan_for_injection(text: str) -> str:
    sanitised, results_valid, _ = scan_prompt([_injection_scanner], text)
    if not all(results_valid.values()):
        raise ValueError(f"Injection pattern detected in cross-agent field — discarded: {text!r}")
    return sanitised
```

**Step 5 — Sign envelopes for cross-service handoffs**

When the sending and receiving agents run as separate services (different processes, containers, or API endpoints), sign the serialised envelope with an HMAC before transmission. The receiver verifies the signature before deserialisation to prevent tampering in transit:

```python
import hashlib, hmac, json, os

_HANDOFF_SECRET = os.environ["AGENT_HANDOFF_SECRET"]   # shared secret, injected at deploy time

def sign_envelope(envelope: ClassifierToBillingEnvelope) -> dict:
    payload = envelope.model_dump_json().encode()
    sig = hmac.new(_HANDOFF_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return {"payload": payload.decode(), "sig": sig}

def verify_and_parse(signed: dict) -> ClassifierToBillingEnvelope:
    payload = signed["payload"].encode()
    expected_sig = hmac.new(_HANDOFF_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, signed["sig"]):
        raise ValueError("Handoff envelope signature mismatch — possible tampering")
    return ClassifierToBillingEnvelope.model_validate_json(payload)
```

*Do not transmit the raw envelope over an unencrypted channel. Use mTLS or a service mesh with identity verification between agents in production.*

**Summary — cross-agent handoff checklist**

| | **Rule** |
|---|---|
| ✓ | Define a dedicated typed envelope per handoff pair |
| ✓ | Use an explicit projection function — never forward a full state dict |
| ✓ | Exclude system prompts, reasoning traces, raw tool output, and debug fields |
| ✓ | Validate the envelope on the receiving side with its own Pydantic model |
| ✓ | Scan all user-derived text fields for injection before prompt inclusion |
| ✓ | Sign envelopes with HMAC for cross-service (multi-process) handoffs |
| ✗ | Never use `state.dict()` or `**kwargs` to populate an envelope |
| ✗ | Never log the raw handoff object — log only the session reference ID |

---

## T — Testability: Current Tools

### Offline evaluation

- **RAGAS** — RAG-specific metrics (groundedness, context relevance, answer relevance)
- **DeepEval** — general LLM eval framework with pytest integration
- **Braintrust** — managed eval platform with dataset versioning
- **DIY:** `pytest` + a JSONL golden dataset file — simple and sufficient for most Level 2 cases

### LLM-as-judge

- Use `gpt-4o` or `claude-sonnet` as judge — more capable than the model being evaluated
- Always calibrate judge against human ratings before trusting scores
- Use structured output for judge scores (not free text ratings)
- Do not use reasoning models (`o3`, `claude-opus`) as judges by default — the reasoning surcharge makes per-sample evaluation expensive; use standard chat models unless the task itself requires it

### Guardrails

- **Guardrails AI** — input/output validation framework
- **LlamaGuard** — Meta's safety classifier, open weights
- **`llm-guard`** — injection-focused input scanner (see Agentic security above); combine with Guardrails AI, not as a replacement
- **Custom:** a lightweight Pydantic model validating output structure is itself a guardrail

### HITL routing

- Route to human review via any task queue: Celery, SQS, Linear, Jira
- Key: include context with escalation (what the model said, why it was escalated, confidence score)
- Track: escalation rate, resolution time, override rate (human agreed vs disagreed with model)

### Audit trail

In addition to escalation metrics, maintain an immutable decision log for each HITL event. The log entry should include:

- Timestamp and unique event ID
- Model output that triggered escalation, including confidence score and escalation reason
- Identity of the human reviewer
- Human decision: accepted, overridden, or deferred
- If overridden: the corrected output
- Retention: minimum **24 months** for regulated domains (finance, healthcare, hiring)

**Append-only storage options:** AWS S3 with Object Lock, Azure Immutable Blob Storage, or a WORM-compliant logging service. Do not use a standard relational DB without row-level append-only enforcement.

> ⚠ **EU AI Act compliance:** For systems classified as high-risk under the EU AI Act, human oversight logs are a legal requirement, not a best practice. Consult legal counsel to confirm retention periods and access controls applicable to your deployment.

---

## Versioning Notes

This document reflects tooling recommendations as of Q2 2026. The following areas are evolving fastest and most likely to change by the next review:

| **Area** | **Outlook** |
|---|---|
| Model pricing | Continued decline expected, especially for frontier models; local 70B routing is now mainstream, not experimental |
| Reasoning model cost models | `budget_tokens` / `reasoning_effort` pricing structures are still settling; providers may introduce separate reasoning token SKUs — verify at each deploy |
| Context-aware caching | Standardisation in progress; expect first-class `SessionContext` support in major caching libraries by Q4 2026 |
| Structured output support | Providers continuing to improve native JSON/schema modes; function calling and tool use APIs converging |
| Agentic security tooling | Injection defence libraries have reached initial maturity; expect consolidation and deeper framework integration through H2 2026 |
| Agentic sandboxing | Effect budget and sandbox constraint patterns are emerging standards; expect LangGraph and similar frameworks to add first-class support |
| Eval tooling | Consolidating; RAGAS, DeepEval, and Braintrust are separating from the field |
| Regulatory compliance (EU/US) | EU AI Act enforcement active; US federal AI governance framework still forming — monitor for changes affecting HITL and audit requirements |

---

*Review date: 2026-Q4*

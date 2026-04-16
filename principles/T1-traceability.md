# T — Traceability & Truth

> **Axiom:** AI systems are opaque. An output without a reproducible input chain is unreliable by definition.

---

## The Problem This Solves

When a traditional function returns a wrong value, you can set a breakpoint, add logging, and trace the execution path. The function is deterministic: same inputs, same outputs, reproducible.

LLMs are different. The same prompt sent twice can produce different outputs. The same model with different temperature settings produces different outputs. The same model identifier (e.g. `"gpt-4"`) can point to different underlying weights after a provider update.

This creates a debugging problem unlike anything in traditional software: **you cannot reproduce a failure without capturing its exact inputs at the time it occurred.**

---

## What Traceability Requires

### 1. Prompt = Code

A prompt that lives in a variable, a config file, or a database field without version history is not a prompt — it's a liability.

**Requirements:**
- Prompts are stored in version control (Git)
- Prompt filenames or identifiers include a version string (`summarize_v2.1.0.txt`)
- Changing a prompt creates a diff, a commit, and optionally a PR
- The prompt version used for each request is logged alongside the response

**Why this matters:** When a regression surfaces in production, the first question is "did the prompt change?" Without version control, you cannot answer this question.

### 2. Model Version Pinning

Model aliases like `"gpt-4"` or `"claude-3-opus"` are pointers that can change. Providers release updates that alter model behavior — sometimes silently.

**Requirements:**
- Every API call uses a fully-qualified model version (e.g. `gpt-4o-2024-08-06`)
- The model version is logged per request
- Model version changes go through the same review process as prompt changes

### 3. Request Correlation

Every AI call must be traceable from the user action that triggered it to the log entry that recorded it.

**Requirements:**
- Generate a unique `request_id` for each AI call
- Propagate this ID through: the API call, the log entry, the database record, and ideally the response to the client
- Log: prompt version, model version, hyperparameters, token counts, timestamp — all in structured format

### 4. RAG Citation Tracking

For retrieval-augmented generation, traceability extends to the retrieval step.

**Requirements:**
- Log the IDs of all document chunks retrieved and injected into context
- Log the retrieval query separately from the generation prompt
- Enable post-hoc groundedness calculation: which claims in the response are supported by which sources?

### 5. Agentic RAG — Reasoning Tree Logging

In Agentic RAG, the model acts as an autonomous search agent: it evaluates retrieved results, decides whether they are sufficient, reformulates the query, and issues follow-up searches. A single user request may trigger 3–10 retrieval steps before generation begins.

Standard single-step RAG logging is insufficient here. If you only capture the final retrieval call, you lose:

- Why the agent abandoned its first query
- Which intermediate results influenced the final context
- Where a reasoning loop or an irrelevant tangent introduced hallucination

**Requirements:**
- Assign a `search_session_id` that groups all retrieval steps belonging to one agent run
- Log each retrieval step as a numbered node in the reasoning tree, including:
  - `step_index` — 0-based position in the search sequence
  - `query` — the reformulated query issued at this step
  - `reasoning` — the model's stated rationale for this query (extracted from tool-call output or chain-of-thought)
  - `chunk_ids` — document chunks retrieved at this step
  - `sufficiency_decision` — `continue` or `stop`, with the model's stated reason
- Log the final context assembly: which chunks from which steps were included in the generation prompt, and in what order
- Preserve the full step tree as a nested structure, not a flat list — order and hierarchy must be reconstructable from the log alone

**Why this matters:** Multi-hop reasoning is where attribution collapses. Without step-level logs, you cannot determine whether a factual error originated from a bad initial query, a poor reformulation at step 3, or a context window truncation at step 5.

### 6. GraphRAG — Knowledge Graph Traversal Logging

GraphRAG replaces or augments vector retrieval with traversal of a knowledge graph. The model extracts seed entities from the query, walks the graph through typed relationships, and assembles context from the resulting node neighborhoods.

**Requirements:**
- Log seed entity extraction: which entities were identified from the user query, their resolved node IDs, and confidence scores
- Log each graph hop:
  - `hop_index` — depth level of this traversal step
  - `source_node` — entity ID and label at the start of the hop
  - `relationship_type` — edge label traversed (e.g. `WORKS_FOR`, `PART_OF`, `HAS_CONDITION`)
  - `target_node` — entity ID and label reached by the hop
  - `hop_score` — relevance or salience score for this edge, if available
- Log the subgraph boundary at each hop depth: the total set of nodes and edges included in context
- Log entity disambiguation decisions when multiple graph nodes match a query term
- Log the final context: which nodes and relationships were serialized into the generation prompt

**Why this matters:** Graph traversal errors are invisible without hop-level logs. A wrong seed entity silently contaminates every downstream hop. An over-broad relationship type (e.g. `RELATED_TO`) can pull in irrelevant subgraphs that look plausible but are semantically incorrect. Without the traversal log, you cannot distinguish a model reasoning error from a retrieval graph error.

---

## The Minimum Viable Trace Log

Every AI call should produce at least this log entry:

```json
{
  "request_id": "a3f2c1d4-...",
  "timestamp": "2025-06-15T14:23:01Z",
  "model": "gpt-4o-2024-08-06",
  "prompt_version": "summarize_v2.1.0",
  "hyperparameters": {
    "temperature": 0.2,
    "max_tokens": 512
  },
  "usage": {
    "input_tokens": 847,
    "output_tokens": 203
  },
  "finish_reason": "stop"
}
```

For RAG, add:

```json
{
  "retrieval": {
    "query": "what is the refund policy for digital goods",
    "chunk_ids": ["doc_42:chunk_7", "doc_18:chunk_2"],
    "retrieved_at": "2025-06-15T14:23:00Z"
  }
}
```

For Agentic RAG, replace the single `retrieval` block with a full reasoning tree:

```json
{
  "search_session_id": "ss_7f3a1c29-...",
  "agent_run_id": "a3f2c1d4-...",
  "steps": [
    {
      "step_index": 0,
      "query": "refund policy digital goods",
      "reasoning": "Initial query derived directly from user intent",
      "chunk_ids": ["doc_42:chunk_7"],
      "sufficiency_decision": "continue",
      "sufficiency_reason": "No explicit time window found in retrieved chunks"
    },
    {
      "step_index": 1,
      "query": "digital goods refund eligibility time limit",
      "reasoning": "Need to locate specific time constraint referenced in doc_42:chunk_7",
      "chunk_ids": ["doc_18:chunk_2", "doc_18:chunk_5"],
      "sufficiency_decision": "stop",
      "sufficiency_reason": "30-day time window confirmed in doc_18:chunk_2"
    }
  ],
  "final_context_chunks": ["doc_42:chunk_7", "doc_18:chunk_2"],
  "total_steps": 2
}
```

For GraphRAG, replace the `retrieval` block with a graph traversal log:

```json
{
  "graph_session_id": "gs_9c1b4e07-...",
  "agent_run_id": "a3f2c1d4-...",
  "seed_entities": [
    { "entity": "DigitalGoods", "node_id": "ent_512", "confidence": 0.94 },
    { "entity": "RefundPolicy", "node_id": "ent_78",  "confidence": 0.89 }
  ],
  "hops": [
    {
      "hop_index": 0,
      "source_node": { "id": "ent_78",  "label": "RefundPolicy" },
      "relationship_type": "APPLIES_TO",
      "target_node":  { "id": "ent_512", "label": "DigitalGoods" },
      "hop_score": 0.91
    },
    {
      "hop_index": 1,
      "source_node": { "id": "ent_78",  "label": "RefundPolicy" },
      "relationship_type": "HAS_CONDITION",
      "target_node":  { "id": "ent_203", "label": "TimeWindow" },
      "hop_score": 0.87
    }
  ],
  "subgraph_nodes": ["ent_78", "ent_512", "ent_203"],
  "final_context_nodes": ["ent_78", "ent_203"]
}
```

---

## Metrics

| Metric | Definition | Target |
|---|---|---|
| **Groundedness Score** | % of factual claims in the response that are directly supported by retrieved documents | > 90% for factual domains |
| **Context Relevance** | Semantic similarity between retrieval query and retrieved chunks | > 0.80 cosine similarity |
| **Prompt Coverage** | % of AI calls where prompt version is logged | 100% — this is non-negotiable |
| **Reasoning Step Coverage** | % of agentic RAG runs where every intermediate search step is logged with query, chunk IDs, and sufficiency decision | 100% |
| **Step Reconstruction Rate** | % of completed agent runs for which the full reasoning tree can be reconstructed from logs alone | > 99% |
| **Graph Hop Coverage** | % of GraphRAG runs with a complete hop-level traversal log (seed entities, edges, scores) | 100% |
| **Seed Entity Precision** | % of seed entities extracted from the query that resolve to relevant nodes in the knowledge graph | > 85% |

---

## Common Objections

**"Logging all this data is expensive."**

Logging metadata (prompt version, token counts, model version) is negligible. You don't need to log the full prompt text for every request — log a hash and keep the prompts in Git. Log full prompts for sampled requests (e.g. 5%) and for all error cases.

**"We use a managed service that handles versioning."**

Managed services version the service, not your prompts. Your prompt content is your business logic — version it yourself.

**"Our prompts are simple, they don't need versioning."**

Simple prompts that work fine are the ones that silently break after a model update. You won't know unless you have the version history to compare.

---

## Further Reading

- [`code-review/traceability-checklist.md`](../code-review/traceability-checklist.md)
- [`examples/traceability/`](../examples/traceability/)

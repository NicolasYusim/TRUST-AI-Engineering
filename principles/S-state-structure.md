# S — Scope & Structure

> Model output and tool requests are untrusted. Authoritative state, authorization, and side effects remain under a deterministic control plane that enforces schemas, least privilege, and action boundaries before execution.

**Review question:** What may the model decide or do, and which code-enforced controls apply before execution?

## Intent

Models may classify, extract, propose plans, choose among permitted tools, and
recommend state transitions. They do not become the authority merely because an
SDK can execute their tool calls.

The control plane owns:

- authoritative workflow and business state;
- identity, tenant, resource, and action authorization;
- schemas and semantic invariants;
- allowed tools, transitions, network destinations, and effect budgets;
- confirmation, idempotency, transaction, and compensation behavior;
- execution and audit of side effects.

## Structured output

Treat model output like any other untrusted request:

1. constrain the provider response with a supported schema when available;
2. validate locally;
3. validate domain invariants and evidence, not only types;
4. handle refusal, truncation, and validation failure explicitly;
5. authorize a validated action against current state;
6. execute only after every required check succeeds.

JSON validity is not schema validity. Schema validity is not semantic truth.

## State

Conversation history is context, not authoritative business state. Persist
workflow state in an owned store, version state transitions, and pass the minimum
necessary projection to the model.

Provider-managed sessions may store conversational state, but they do not replace
the application's source of truth or authorization layer.

## Bounded orchestration

An agentic node may choose only among capabilities declared by code. A sandbox
contract includes:

- allowed tools and resource scopes;
- allowed transitions;
- input, output, and tool-argument schemas;
- per-tool and total effect limits;
- required confirmation and authorization policies;
- idempotency and rollback/compensation strategy;
- maximum steps, time, and resource use.

Validate the complete proposed action or plan before side effects. A preflight
counter does not make several external calls transactional; adapters must use a
real transaction or explicit compensation where atomicity matters.

## What this principle does not guarantee

- that structured values are factually correct;
- that a prompt instruction is an authorization control;
- that an allowlisted tool is safe for every user or resource;
- that an effect budget prevents duplicate or partially committed effects;
- that injection scanners make untrusted content safe.

## Review checklist

Use [`code-review/state-structure-checklist.md`](../code-review/state-structure-checklist.md).
Offline references:
[`examples/state-structure/correct.py`](../examples/state-structure/correct.py) and
[`examples/state-structure/sandbox_correct.py`](../examples/state-structure/sandbox_correct.py).

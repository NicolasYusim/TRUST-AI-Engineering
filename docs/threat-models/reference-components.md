# Reference-component threat model

Scope: the committed, offline Python reference implementations. This document
does not cover a production model provider, network, identity service, storage
adapter, deployment platform, or monitoring backend. An integration must extend
the model before it may reuse an `enforced` production claim.

## Shared trust boundaries

- Prompts, source documents, retrieved records, graph contents, model output, and
  proposed tool calls are untrusted.
- Local schemas, deterministic validators, approved-source collections, tenant
  context, and effect adapters form the trusted control plane.
- Test fixtures and JSON result artifacts are evidence only for the committed
  offline population.
- Provider credentials are out of scope: the reference adapters use no secrets.

## Component analysis

| Component | Principal threats | Enforced boundary | Residual risk / integration work |
|---|---|---|---|
| `code-generator` | unsafe code, provider failure, fallback budget exhaustion | AST screening, no generated-code execution, one total deadline | isolate any production execution and add provider/network controls |
| `document-summarizer` | trace tampering, sensitive payload leakage, cross-tenant artifacts | content-addressed references and strict logical artifact separation | add access control, encryption, deletion, and retention enforcement |
| `faq-answerer` | poisoned FAQ content, cache crossover, unbounded generation | versioned published FAQs, tenant/locale cache keys, reference-token bound | approve the production knowledge pipeline and monitor cache isolation |
| `graphrag-answerer` | poisoned nodes/edges, hidden traversal, tenant crossover | allowlisted relations and a complete versioned traversal trace | authenticate graph updates and enforce storage-level tenant predicates |
| `job-data-extractor` | schema bypass, fabricated evidence, invalid field relations | local type/domain validation and non-empty source-quote resolution | classify source documents and test adversarial production formats |
| `support-answer-generator` | unsupported claims, unapproved sources, prompt injection | approved in-memory articles, citation validation, explicit abstention | add authenticated retrieval and source-lifecycle governance |
| `support-ticket-triage` | confident misrouting, distribution shift, ambiguous tickets | versioned offline gate and manual review for unknown cases | measure production slices, drift, calibration, and downstream authority |
| `support-ticket-router` | tenant crossover, forged confirmation, excessive agency, duplicate effects, partial writes, missing audit | identity/tenant/resource authorization; plan-bound confirmation; payload-bound idempotency; pre-effect validation; rollback; metadata-only audit and alert signals | replace in-memory atomicity and alert sink with independently verified production adapters |

## High-consequence abuse cases: support-ticket-router

The high-consequence write example must fail closed for each of these cases:

1. A confirmation is absent, belongs to another identity or tenant, or refers to
   a different canonical plan hash.
2. A ticket, queue, template, tool, transition, or effect count is outside the
   authenticated scope.
3. An idempotency key is reused with a different plan payload.
4. An adapter fails after a partial in-memory effect.
5. A blocked, conflicting, or failed action is not represented by an audit event
   and an alert signal.

The executable tests named by its manifest exercise these cases. The manifest
also binds those test IDs to its blocking metric and suite hash.


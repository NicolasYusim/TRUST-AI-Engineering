# T.R.U.S.T.
### Production-Ready AI Engineering Doctrine

---

```
T — Traceability    Every AI output must be reproducible from its inputs.
R — Resilience      AI is an unreliable external node. Design for failure.
U — Utility         Every AI call consumes resources. Justify it.
S — Strict Contracts  AI is a calculator, not an orchestrator. Use schemas.
T — Testability     Measure before you ship. Escalate what you can't measure.
```

---

## Why T.R.U.S.T. Exists

Most AI engineering guides describe **tools**: specific models, APIs, libraries. They become outdated in 18 months. T.R.U.S.T. describes the **nature of AI systems** — opacity, unreliability, cost, statelessness, fallibility. These properties will not disappear in 10 or 30 years.

**The test:** Take any principle and remove all technical nouns. It must survive. If it doesn't — it's a recipe, not a principle.

T.R.U.S.T. is structured in two layers:

```
AXIOMS      — timeless, language-agnostic, never change
    ↓
PRACTICES   — versioned, dated, reviewed every 6 months
```

This repository contains the axioms. The practices are in [`docs/practices-2026-Q2.md`](docs/).

---

## The Five Axioms

### T — Traceability & Truth

> **Axiom:** AI systems are opaque. An output without a reproducible input chain is unreliable by definition.

The system configuration that produced a result must be recorded alongside the result. Every generated fact or function call must be explainable: where did the AI get the data, and what configuration produced the answer.

**The eternal code review question:**
> *"Can I accurately reconstruct why the system gave this answer?"*

**Violation visible in code:**
The system configuration is not recorded alongside the result of the call.

---

### R — Resilience & Responsibility

> **Axiom:** An AI component is a probabilistic external service. It cannot be a single point of failure. Every degradation must have an owner.

Treat the neural network as an unstable external node. The architecture must intercept failures. The AI component cannot be an "orphan" — its metrics must have a responsible engineer.

**The eternal code review question:**
> *"What does the system do when AI is unavailable? Who is responsible for this?"*

**Violation visible in code:**
An AI call failure leads to an unhandled exception in the code.

---

### U — Unit Economics & UX

> **Axiom:** AI computation always consumes resources — computational, time, financial, energetic. An unjustified call is an architectural defect.

AI must be economically controllable. 300ms and 3 seconds of waiting are different products. Uncontrolled requests kill the business on API bills.

**The eternal code review question:**
> *"Is this call justified by the complexity of the task?"*

**Violation visible in code:**
The most powerful available AI is called for a task that can be solved in a simpler way.

---

### S — State & Structure

> **Axiom:** LLM is a calculator without memory and without the right to orchestrate. The boundary between AI and business logic must be machine-verifiable.

The illusion is making AI hold long logic chains in memory through prompts alone. Interaction with business logic must go through strict contracts. The model makes a decision only within a node; the transition to the next step is dictated by code.

**The eternal code review question:**
> *"Can a validator check the output of this AI component without human intervention?"*

**Violation visible in code:**
Business logic is applied to text that the AI "meant", rather than a structure it was obligated to output.

---

### T — Testability & Trust

> **Axiom:** AI makes mistakes. A change without measurement is a blindly accepted risk. High-stakes decisions require a human in the loop.

Any change is evaluated by numbers before production. Guardrails must be measurable, and dangerous cases are routed to a human.

**The eternal code review question:**
> *"How can I prove with numbers that this change did not degrade the system?"*

**Violation visible in code:**
A system configuration change is deployed without running it against control test cases.

---

## Maturity Levels

T.R.U.S.T. should not cause overengineering from day one. The framework is introduced as the product matures:

| Level | Stage | Apply |
|-------|-------|-------|
| 1 | **MVP** | S (strict schemas), basic U (watch API limits), T (log config) |
| 2 | **Product-Market Fit** | + T (offline eval), R (fallbacks), metric ownership |
| 3 | **Enterprise** | Full coverage: guardrails, HITL, RAG evals, shadow mode |

→ See [`docs/maturity-levels.md`](docs/maturity-levels.md) for detail.

---

## Repository Structure

```
trust-framework/
│
├── README.md                        ← You are here. The manifest.
├── PRINCIPLES.md                    ← Condensed one-page reference
│
├── principles/                      ← Deep dives into each axiom
│   ├── T1-traceability.md
│   ├── R-resilience.md
│   ├── U-unit-economics.md
│   ├── S-state-structure.md
│   └── T2-testability.md
│
├── code-review/                     ← Checklists for PR reviews
│   ├── README.md
│   ├── traceability-checklist.md
│   ├── resilience-checklist.md
│   ├── unit-economics-checklist.md
│   ├── state-structure-checklist.md
│   └── testability-checklist.md
│
├── examples/                        ← Violation → Correct implementation pairs
│   ├── README.md
│   ├── traceability/
│   ├── resilience/
│   ├── unit-economics/
│   ├── state-structure/
│   └── testability/
│
└── docs/                            ← Philosophy, practices, changelog
    ├── philosophy.md
    ├── maturity-levels.md
    └── practices-2025-Q2.md
```

---

## Contributing

T.R.U.S.T. is a living doctrine with a strict separation:

- **Axioms** (`principles/`) — open a Discussion before proposing a change. The bar is high.
- **Practices** (`docs/practices-*.md`) — PR welcome, especially with real-world data.
- **Examples** (`examples/`) — PRs with new language implementations warmly accepted.

---

*Axioms don't change. Practices get versioned.*

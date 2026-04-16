# Philosophy

## Why Another AI Framework?

There are many guides to working with LLMs. Most of them tell you which tools to use, which models to call, which libraries to import. They are detailed, practical, and immediately useful.

They are also wrong in 18 months.

The AI tooling landscape changes faster than any other area of software engineering right now. A guide written around a specific model, a specific API shape, or a specific set of libraries becomes a historical document quickly. Engineers who followed it closely find themselves having learned the specifics without having absorbed the underlying reasoning.

T.R.U.S.T. is an attempt to separate two things that are usually conflated:

**Axioms** — true statements about the nature of AI systems that will remain true regardless of how the tooling evolves.

**Practices** — current best implementations of those axioms, using today's tools, at today's prices, with today's model capabilities.

---

## The SOLID Analogy

SOLID has survived 25 years because it describes invariants in how software grows and how human cognition works — not invariants in any particular language or framework.

The Single Responsibility Principle is not about classes. It's about the observation that things which change for different reasons should be separated, because coupling them creates work. This observation is true in Python, in Go, in functional programming, in 1995 and in 2025.

T.R.U.S.T. attempts the same for AI integration. Each axiom describes a property of AI systems that is not contingent on current tooling:

- **Opacity** (Traceability): AI systems do not expose their reasoning. This was true of GPT-2 and will be true of systems far more capable than GPT-4o.
- **Unreliability** (Resilience): Probabilistic systems fail in unpredictable ways. External services have outages. This is not a temporary property of current APIs.
- **Resource consumption** (Unit Economics): Computation costs something. Time costs something. This will remain true even as costs decline — the optimization calculus changes, the principle does not.
- **Statelessness** (State & Structure): A model call is a function call: inputs in, output out. The model does not persist memory between calls unless you explicitly pass it. This is architectural, not incidental.
- **Fallibility** (Testability): AI makes mistakes. The error rate changes over time, but the existence of errors does not. Measurement is non-optional.

---

## What T.R.U.S.T. Is Not

**It is not a silver bullet.** Applying T.R.U.S.T. does not guarantee a good AI integration. It prevents specific, common, expensive failure modes. The hard parts of building good AI products — product intuition, evaluation design, domain expertise — are not addressed by any framework.

**It is not a checklist to apply blindly.** The maturity levels exist for a reason. Applying Enterprise-level observability to an MVP is waste, not discipline. Judgment about what to apply and when is irreducible.

**It is not prescriptive about tools.** The examples use Python, Pydantic, and OpenAI because these are common. The principles apply equally to TypeScript, Zod, and Anthropic — or to any stack that doesn't exist yet.

**It is not static.** The axioms are stable. The practices — the specific tools, metrics, thresholds, and patterns — will be revised as the landscape changes. The versioning of `docs/practices-*.md` is intentional.

---

## The Operational Definition of a Principle

A principle in T.R.U.S.T. must satisfy three tests:

1. **It survives noun removal.** Strip all technical nouns (model names, library names, API names) from the principle. The core idea must remain meaningful.

2. **Its violation is visible in code.** You should be able to point to a specific line or absence of code and say "this violates the principle." If violation requires running the system to detect, it's a metric, not a principle.

3. **It is falsifiable.** There must be concrete code that satisfies the principle and concrete code that violates it. If everything is "it depends," it's a discussion topic, not a principle.

Every axiom in T.R.U.S.T. passes these three tests. If you want to propose a new axiom, it must pass them too.

---

## On Overengineering

The maturity levels exist because the costs and benefits of each principle vary with the stakes involved.

A prompt that's hardcoded in a startup's MVP is not a violation of Traceability — it's appropriate for the current stakes. That same hardcoded prompt in a healthcare product processing 100,000 calls per day is a serious liability.

The principle is the same. The appropriate implementation changes with context.

T.R.U.S.T. does not say "always do everything." It says "understand the principles, understand your context, and apply the right level of rigor for the current stakes." The engineer's judgment is not replaced — it's given a framework to operate within.

---

## Further Reading

- [`README.md`](../README.md) — The manifest
- [`docs/maturity-levels.md`](maturity-levels.md) — When to apply what
- [`docs/practices-2025-Q2.md`](practices-2025-Q2.md) — Current tool recommendations

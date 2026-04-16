# T.R.U.S.T. — Principles Reference Card

> Print this. Put it next to your monitor.

---

## T — Traceability
*AI systems are opaque. An output without a reproducible input chain is unreliable by definition.*

| | |
|---|---|
| **Rule** | No logs = hallucination |
| **Question** | Can I reconstruct why the system gave this answer? |
| **Violation** | Config not recorded alongside result |

---

## R — Resilience
*AI is a probabilistic external service. It cannot be a single point of failure. Every degradation must have an owner.*

| | |
|---|---|
| **Rule** | LLM fails by default. Find the owner of the fallback. |
| **Question** | What does the system do when AI is unavailable? |
| **Violation** | AI failure → unhandled exception |

---

## U — Utility
*AI computation always consumes resources. An unjustified call is an architectural defect.*

| | |
|---|---|
| **Rule** | Count tokens and milliseconds. |
| **Question** | Is this call justified by the complexity of the task? |
| **Violation** | Most powerful model called for a trivial task |

---

## S — Strict Contracts
*LLM is a calculator without memory. The AI/business-logic boundary must be machine-verifiable.*

| | |
|---|---|
| **Rule** | State outside. Data in structures. Never parse text. |
| **Question** | Can a validator check this output without a human? |
| **Violation** | Business logic applied to text the AI "meant" |

---

## T — Testability
*AI makes mistakes. A change without measurement is a blindly accepted risk.*

| | |
|---|---|
| **Rule** | If you didn't measure it, don't deploy it. |
| **Question** | How do I prove this change didn't degrade the system? |
| **Violation** | Config change deployed without running control test cases |

---

*For the full axiom explanations, see [`README.md`](README.md). For code examples, see [`examples/`](examples/).*

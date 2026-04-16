# Examples: Violation → Correct Implementation

Each subdirectory contains a pair of files:

- `violation.py` — code that **violates** the principle. Annotated with comments explaining what's wrong.
- `correct.py` — the same scenario, implemented correctly. Annotated with what changed and why.

Examples are written in Python but the patterns apply to any language.

---

## Index

| Principle | Scenario | What you'll learn |
|---|---|---|
| [Traceability](traceability/) | Prompt versioning + request logging | How to make AI calls reproducible and debuggable |
| [Resilience](resilience/) | Quality-gated escalation | How to try a cheap model first and escalate to a reasoning model only when output validation fails |
| [Unit Economics](unit-economics/) | Model routing + semantic cache | How to cut costs 80%+ without degrading quality |
| [State & Structure](state-structure/) | Structured output + retry | How to stop parsing AI text and use validated schemas |
| [Testability](testability/) | Offline eval + HITL escalation | How to gate deploys on measured quality |

---

## Reading the Examples

Both files in each pair describe the **same feature**. The violation is not "bad code written by a junior" — it's the kind of code a thoughtful engineer writes without knowing the T.R.U.S.T. principles. The correct version is a refactor, not a rewrite.

Look for the `# ❌` and `# ✅` annotations.

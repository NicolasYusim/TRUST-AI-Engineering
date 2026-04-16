# Code Review Checklist — T: Testability

> **Axiom:** AI makes mistakes. A change without measurement is a blindly accepted risk. High-stakes decisions require a human in the loop.
>
> **The eternal question:** *"How can I prove with numbers that this change did not degrade the system?"*

---

## Before Approving a PR, Confirm:

### 1. Offline evaluation exists

- [ ] A **golden dataset** exists for the affected AI component (input → expected output pairs)
- [ ] The PR includes eval results, or points to a CI run where evals passed
- [ ] The golden dataset covers: happy path, edge cases, and known failure modes
- [ ] Eval metrics are defined before the change, not chosen after seeing results

### 2. Metrics are defined and tracked

- [ ] At least one **task-specific metric** is defined (e.g. accuracy, F1, BLEU, exact match, LLM-as-judge score)
- [ ] The metric has a documented **threshold** below which the change is rejected
- [ ] Metrics are stored and comparable across versions (regression detection)

### 3. Online metrics are monitored post-deploy

- [ ] Task Success Rate is tracked in production (not just error rate)
- [ ] There is an alert if the online metric drops significantly after deploy
- [ ] Hallucination rate or groundedness score is monitored (for RAG / factual tasks)

### 4. Escalation policy (HITL) is defined for high-stakes components

- [ ] Low-confidence outputs are identified and handled (not silently passed through)
- [ ] There is a defined confidence threshold below which the case escalates to a human
- [ ] Safety triggers (bias detection, injection detection) route to human review or explicit refusal
- [ ] False Positive Rate and False Negative Rate of guardrails are tracked

### 5. Guardrails are measurable

- [ ] Input/output guardrails are tested in the eval suite — not just enabled in production
- [ ] FPR (blocking a legitimate request) is monitored and has an acceptable threshold
- [ ] FNR (passing a harmful/invalid request) is monitored and has an acceptable threshold

---

## Red Flags to Block a PR

```
❌  "I tested it manually, looks good"
❌  # no eval dataset, no metrics, prompt changed and shipped
❌  # guardrails added but never tested for false positives
❌  # no confidence scoring, all outputs treated as equally reliable
❌  # no monitoring, we'll find out about regressions from user complaints
```

## Green Flags

```
✅  # eval run in CI
    results = run_eval(
        dataset="golden/summarization_v3.jsonl",
        metric=RougeL(),
        threshold=0.72
    )
    assert results.score >= results.threshold, f"Eval failed: {results}"

✅  # confidence gating
    if response.confidence < HITL_THRESHOLD:
        return escalate_to_human(session_id, response)

✅  # online metric dashboard
    metrics.gauge("task_success_rate", value=tsr, tags={"component": "summarizer"})
    alert_if_below(metric="task_success_rate", threshold=0.90, window="10m")

✅  # guardrail test
    assert guardrail.check(NORMAL_INPUTS) == ALLOW   # FPR test
    assert guardrail.check(INJECTION_INPUTS) == BLOCK # FNR test
```

---

## Offline vs Online Metrics

| | Offline (Eval) | Online (Prod) |
|---|---|---|
| When | Before deploy | After deploy |
| Data | Golden dataset | Real user traffic |
| Purpose | Prevent regression | Detect drift |
| Examples | Accuracy, F1, ROUGE | TSR, hallucination rate, CSAT |
| Action on failure | Block the deploy | Alert → investigate → rollback |

Both are required. Offline eval without online monitoring misses distribution shift. Online monitoring without offline eval means you find regressions from users.

---

## Questions to Ask the Author

1. *"What golden dataset was this change evaluated against?"*
2. *"What metric threshold would cause this PR to be rejected?"*
3. *"How will we know in 48 hours if this change made things worse in production?"*
4. *"Is there any output from this component that goes directly to a consequential action without human review?"*

---

→ See [`examples/testability/`](../examples/testability/) for violation and correct implementation side-by-side.

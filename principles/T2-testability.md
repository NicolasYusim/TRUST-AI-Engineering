# T — Testability & Trust

> **Axiom:** AI makes mistakes. A change without measurement is a blindly accepted risk. High-stakes decisions require a human in the loop.

---

## The Problem This Solves

AI systems have a quality problem that doesn't exist in traditional software: the output quality degrades silently. A bug in a traditional function usually throws an exception or produces an obviously wrong value. A regression in an AI component produces outputs that are subtly worse — less accurate, more hallucinated, slightly off-tone — in ways that don't trigger alerts and can take weeks to surface through user complaints.

The Testability principle says: **you must have a measurement infrastructure before you ship, not after you notice something is wrong.**

---

## Two Measurement Regimes

### Offline Evaluation (before deploy)

Offline eval answers the question: *"Is this version of the AI component better or equal to the previous version?"*

**Components:**
1. **Golden dataset** — a curated set of (input, expected output) pairs that cover the range of production use cases
2. **Evaluation metrics** — quantitative measures of quality appropriate to the task
3. **Threshold** — the minimum acceptable metric value, defined before running the eval
4. **CI integration** — the eval runs automatically and blocks the deploy if it fails

**Golden dataset requirements:**
- Must include: happy path, edge cases, known failure modes, adversarial inputs
- Must be reviewed and updated when the task definition changes
- Safety-critical cases (if any) should be tagged — a failure on these is always blocking
- Minimum viable size: 50–100 human-curated seed cases. Extend to 1,000+ through synthetic generation (see below).

**Synthetic data generation (required for scale):**

Manual curation is a bottleneck. In 2026, using a strong LLM to expand the dataset is standard practice. Seed cases are written by humans; a generation pipeline multiplies them across rare edge cases and adversarial inputs automatically.

**Generation pipeline:**
1. **Seed** — collect 50–100 human-verified (input, expected output) pairs
2. **Expand** — prompt a capable LLM to produce variants: paraphrases, domain shifts, language mixing, adversarial rewrites, boundary-value inputs
3. **Filter** — run a separate LLM-as-Judge pass to reject low-quality or duplicate generations; keep only cases that pass schema and quality thresholds
4. **Freeze** — commit the generated dataset to version control; regenerate on task definition changes, not on every eval run
5. **Tag** — mark each case with source (`human` | `synthetic`) and category (`happy-path` | `edge-case` | `adversarial` | `safety-critical`)

**Target dataset composition:**

| Source | Minimum count | Purpose |
|---|---|---|
| Human-curated seed | 50–100 | Ground truth anchor, judge calibration |
| Synthetic — edge cases | 500+ | Rare but valid inputs |
| Synthetic — adversarial | 300+ | Prompt injection, jailbreaks, boundary inputs |
| Synthetic — safety-critical | 100+ | Must-pass cases; any failure is always blocking |

**Generation prompt pattern (example):**

```
You are generating eval cases for [task description].
Seed input: [example]
Generate 10 variants that test: {edge_case_type}.
Each variant must be realistic, distinct, and solvable by the target model.
Output: JSON array of {"input", "expected_output", "category"} objects.
```

**Guardrails on generated data:**
- Never use generated cases as the sole ground truth for safety-critical scenarios — human review is required
- Track the synthetic-to-human ratio in eval reports
- Flag if the judge pass rate drops below 70% — this indicates the generation prompt is degrading

### Online Metrics (after deploy)

Online metrics answer: *"Is the system working correctly in production right now?"*

**Key metrics by task type:**

| Task type | Primary metric | Secondary metric |
|---|---|---|
| Classification | Task Success Rate | F1 by class |
| Extraction | Field accuracy | Schema compliance rate |
| Summarization | User feedback rate | Groundedness score |
| RAG Q&A | Answer relevance | Hallucination rate |
| Agentic | Task completion rate | Fallback escalation rate |

**Alert thresholds should be set based on offline eval baselines.** If your eval shows 94% accuracy, alert in production at < 90% — not at < 50%.

### Async LLM-as-a-Judge in Production (2026 Practice)

Running a judge model on every production request is cost-prohibitive. The standard approach is a decoupled async evaluation pipeline that operates on a sampled fraction of traffic.

**Why you cannot judge 100% of requests:**
- A judge call costs the same order of magnitude as the original call — doubling inference cost for full coverage is rarely justified
- Judge latency must not be on the critical path: the user response must not wait for evaluation
- High-volume endpoints (e.g. autocomplete, embeddings) produce more logs than can be judged in real time at any cost

**Architecture: async sampling pipeline**

```
Production request
      │
      ▼
  Main model call ──► Response to user
      │
      ▼
  Log to WORM storage (S3 / GCS immutable bucket)
      │
      ▼  (async, off critical path)
  Sampling worker (Celery / Kafka consumer)
      │  samples ~5% of logs, configurable per endpoint
      ▼
  Judge model call (smaller / cheaper model)
      │  scores: relevance, groundedness, hallucination flags
      ▼
  Metrics store (time-series DB)
      │
      ▼
  Dashboard + drift alerts
```

**Sampling strategy:**
- Default: random 5% sample across all requests
- Priority overrides: always judge if `confidence < threshold`, `fallback_triggered = true`, or input matches a monitored topic tag
- Stratified sampling: ensure rare request categories (e.g. non-English, edge-case intents) are not systematically excluded — sample at a higher rate from low-frequency buckets if needed

**WORM storage requirement:**  
Logs must be written to an immutable (Write Once Read Many) store before the async worker reads them. This guarantees the sample reflects exactly what the model received and produced — not a post-hoc reconstruction. Log entries must include: `request_id`, `timestamp`, `model_version`, `prompt`, `response`, `retrieved_context` (for RAG), `latency_ms`.

**Judge model selection:**
- Use a model 1–2 tiers cheaper than the production model (e.g. production on GPT-4o → judge on GPT-4o-mini; production on Claude Sonnet → judge on Claude Haiku)
- The judge prompt must be fixed and versioned — judge prompt changes require re-calibration against human ratings before deployment
- Calibrate periodically: take 200 random judged samples, have a human rate them, measure judge–human agreement (target Cohen's κ > 0.7)

**Metrics produced by the pipeline:**

| Metric | How computed | Drift alert condition |
|---|---|---|
| Hallucination rate | Judge flags unsupported claims / total judged | > baseline + 3σ over 1h window |
| Groundedness score | Judge rates source support 1–5, average | < baseline − 0.3 over 6h window |
| Task Success Rate proxy | Judge binary pass/fail on rubric | < baseline − 5pp over 24h window |
| Judge confidence distribution | Fraction of low-confidence judge scores | > 20% triggers human review |

**Operational notes:**
- Worker backpressure: if the judge queue exceeds a depth threshold, increase sample interval rather than dropping logs — dropped logs create survivorship bias in the metrics
- Separate queues per endpoint criticality: high-stakes endpoints (e.g. medical, financial) run at 10–20% sampling; low-stakes endpoints at 1–2%
- Cost cap: set a hard daily budget on the judge model; alert if the cap is approached so sampling rate can be reduced rather than silently stopped
- Replay capability: because logs are immutable, you can re-run historical samples through a new judge version to compare scores before switching — treat judge upgrades like model upgrades, with a calibration step

---

## Evaluation Metrics Reference

### Task Success Rate (TSR)
The fraction of production AI calls that resulted in the intended outcome. Requires some ground truth signal (user confirmation, downstream validation, human rating).

### Groundedness Score
For RAG: the fraction of factual claims in the response that are directly supported by the retrieved context. Computed post-hoc from logs.

### LLM-as-Judge
For tasks where ground truth is hard to define (e.g. tone, helpfulness), use a separate LLM call to evaluate the response against a rubric. Calibrate the judge against human ratings before trusting it.

### ROUGE / BERTScore
For summarization. ROUGE measures n-gram overlap with reference summaries. BERTScore uses embeddings for semantic similarity. Use these as approximate signals, not ground truth.

---

## Human-in-the-Loop (HITL) Escalation

Some decisions should not be made by a model alone, regardless of its measured accuracy. HITL escalation is not a fallback for poor performance — it's a design choice for high-stakes domains.

**When to escalate to a human:**
1. **Low confidence** — the model's own confidence score is below a threshold
2. **Safety triggers** — the input matches patterns that indicate sensitive content
3. **High-stakes outcome** — the AI's decision has irreversible or significant consequences
4. **Novel input** — the input is outside the distribution of the training/eval data

**Escalation should be:**
- Fast: the human should receive context, not just the raw input
- Logged: escalation events are data — track rate, reason, and resolution
- Measured: FPR (escalating legitimate cases) and FNR (missing cases that needed escalation) are metrics

---

## Guardrails: The Defense Layer

Guardrails are classifiers that run before or after the main model call to detect problematic inputs or outputs.

**Types:**
- **Input guardrails:** detect prompt injection, out-of-scope requests, PII
- **Output guardrails:** detect hallucinations, policy violations, sensitive content

**Guardrails must be tested independently**, using their own eval dataset. A guardrail with a high False Positive Rate blocks legitimate users. A guardrail with a high False Negative Rate provides false security.

```
Guardrail metrics to track:
- FPR (False Positive Rate): legitimate requests blocked
- FNR (False Negative Rate): harmful/invalid requests passed through
- Latency added: guardrails add to TTFT — measure and optimize
```

---

## The Eval-Deploy Gate

This is the single most important practice in this principle:

```
No AI component change ships to production
without a documented eval run showing the change
does not regress quality below the defined threshold.
```

"Change" means: prompt update, model version update, retrieval system update, hyperparameter change, guardrail threshold change.

**Enforcement:**
- Eval runs in CI as an automated test
- Eval results are stored and linked to the deployment
- Manual override requires explicit approval with documented justification

---

## The Offline / Online Split in Practice

```
Before deploy:
  1. Run offline eval on golden dataset
  2. Check: accuracy >= threshold? Safety cases pass?
  3. If yes: deploy with canary (5% traffic)
  4. Monitor online metrics for 1 hour
  5. If metrics stable: expand rollout

After full deploy:
  6. Monitor online metrics continuously
  7. Alert if metrics drop below threshold
  8. Revert capability: keep previous version deployable for 48h
```

---

## Failure Modes in Eval Design

**Threshold shopping:** Running eval, seeing the score, then setting the threshold below the score. The threshold must be set before the eval run.

**Leakage:** Golden dataset examples that were used during prompt development. The eval dataset must be held out from prompt iteration.

**Metric gaming:** Optimizing the metric rather than the actual task quality. Use multiple metrics and occasionally review outputs qualitatively.

**Stale golden dataset:** The golden dataset doesn't reflect production distribution changes. Re-run the synthetic generation pipeline quarterly or after significant task definition changes; update seed cases when new failure modes are discovered in production.

**Synthetic data quality drift:** The generation LLM's behavior can shift between runs, producing different distributions. Freeze generated datasets in version control — do not regenerate on every eval run.

---

## Further Reading

- [`code-review/testability-checklist.md`](../code-review/testability-checklist.md)
- [`examples/testability/`](../examples/testability/)

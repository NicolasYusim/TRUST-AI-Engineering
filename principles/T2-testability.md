# T2 — Testability & Oversight

> AI changes are evaluated on versioned evidence with metrics and oversight proportional to consequence. Uncertainty is calibrated independently; high-risk actions require abstention, review, or another effective control.

**Review question:** What evidence shows this change meets its quality and risk thresholds?

## Intent

AI quality can regress without an exception. Testability makes the expected
behavior, evaluation population, metrics, thresholds, and deployment decision
reviewable and repeatable.

## Evaluation contract

For every material model, prompt, retrieval, policy, or guardrail change:

- identify the versioned evaluation suite and its intended population;
- predeclare task, safety, slice, latency, and cost metrics;
- label numeric thresholds by evidence basis;
- separate development data from held-out evaluation evidence;
- record the candidate, baseline, environment, result, and decision;
- block, abstain, route, or require approval when the contract fails.

Synthetic cases can expand coverage but must be labelled and must not be the sole
ground truth for consequential decisions. LLM-as-judge results require
calibration against suitable independent ratings.

## Uncertainty

A number produced by the same model is not calibrated confidence by default.
Useful uncertainty signals may include held-out calibration, ensemble
disagreement, retrieval support, conformal methods, out-of-distribution
detection, deterministic validation, or human review.

## Oversight

Oversight is risk control, not ceremony. Depending on consequence it may mean:

- abstention or fail-closed behavior;
- review by a qualified person with enough context and time;
- dual approval for irreversible actions;
- deterministic policy or independent validator;
- canary/shadow deployment and automated rollback.

Measure reviewer agreement, override rate, missed escalations, queue latency, and
automation bias where applicable.

## Online evidence

Monitor production outcomes and distribution shift using privacy-aware samples
and downstream signals. Sampling rates and alert thresholds must be calibrated
to traffic, rarity, and consequence rather than copied as universal constants.

## What this principle does not guarantee

- that a large dataset represents production;
- that accuracy is sufficient for asymmetric risk;
- that model self-confidence is calibrated;
- that human review always reduces risk;
- that passing an eval proves safety outside its stated population.

## Review checklist

Use [`code-review/testability-checklist.md`](../code-review/testability-checklist.md).
The offline support-routing reference is
[`examples/testability/correct.py`](../examples/testability/correct.py).

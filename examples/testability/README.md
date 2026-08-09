# Testability example

The previous medical-triage scenario was removed. This directory now uses a
low-consequence support-ticket routing fixture.

## Guarantees

- Baseline and candidate use the same committed JSONL suite.
- The blocking threshold is supplied before evaluation.
- Unknown cases abstain to a manual-review status.
- Reported repository metrics are reproducible by tests.

## Does not guarantee

- production representativeness;
- fairness across unrepresented slices;
- calibrated model confidence;
- suitability for medical, legal, financial, employment, or safety use.

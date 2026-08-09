# T2 review — Testability & Oversight

> AI changes are evaluated on versioned evidence with metrics and oversight proportional to consequence. Uncertainty is calibrated independently; high-risk actions require abstention, review, or another effective control.

**Review question:** What evidence shows this change meets its quality and risk thresholds?

## Block approval until

- [ ] A versioned suite describes its intended population and important slices.
- [ ] Metrics and thresholds were declared before the candidate result was seen.
- [ ] Thresholds and numeric claims include an evidence basis.
- [ ] Development examples are separated from held-out evaluation evidence.
- [ ] Safety/consequence metrics reflect asymmetric failure cost.
- [ ] Synthetic data and LLM-judge results are labelled and independently checked.
- [ ] Model self-confidence is not treated as calibrated without evidence.
- [ ] Abstention, review, deterministic control, or rollback matches the risk.
- [ ] The eval gate is automated for the component's declared tier.
- [ ] Production monitoring can detect drift beyond the offline population.

## Evidence expected in the PR

- updated `trust.yaml`;
- baseline/candidate eval report;
- calibration or oversight evidence where used;
- link to any exception.

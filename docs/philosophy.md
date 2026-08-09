# Philosophy

## Why T.R.U.S.T. exists

General governance and security frameworks describe broad outcomes across an AI
system lifecycle. Engineering teams still need a small vocabulary for pull
requests, component ownership, failure behavior, authority boundaries, and
evaluation gates.

T.R.U.S.T. is that engineering layer. Its contribution is compression and
operationalization, not a claim that provenance, resilience, cost control,
least privilege, or evaluation are new ideas.

## Durable principles and changing practices

The five principles are intended to remain useful across provider and tooling
changes. They are durable, not immutable. A recorded decision may refine them
when evidence shows that wording is ambiguous, unsafe, or incomplete.

Practices, provider facts, thresholds, mappings, and examples change more often:

- durable definitions live in [`../framework/principles.yaml`](../framework/principles.yaml);
- current implementation guidance lives in
  [`practices_2026_Q3.md`](practices_2026_Q3.md);
- provider facts live in [`../registry/models.yaml`](../registry/models.yaml);
- control requirements live in
  [`../policies/risk-tiers.yaml`](../policies/risk-tiers.yaml);
- decisions and exceptions are recorded in
  [`decisions-and-exceptions.md`](decisions-and-exceptions.md).

## Operational test

A T.R.U.S.T. principle should:

1. remain meaningful after provider and library names are removed;
2. imply reviewable controls in code, configuration, evidence, or operations;
3. distinguish what the control guarantees from what it does not guarantee;
4. scale with consequence, authority, data sensitivity, and exposure;
5. be testable through declared evidence, not assertion alone.

Not every violation is visible in a single code line. Missing evaluation evidence,
weak ownership, and uncalibrated thresholds can be repository or operational
failures. The component manifest makes those absences reviewable.
Structural declarations are checked by `trust lint`; repository evidence,
hashes, observed results, exceptions, and executable suites are checked by
`trust verify`.

## What the framework is not

T.R.U.S.T. is not:

- a safety or correctness guarantee;
- a regulatory certification;
- a replacement for secure software development;
- a universal collection of model, timeout, or metric defaults;
- a reason to log sensitive data without a lawful purpose and retention policy;
- a prohibition on agents or model-driven planning.

It allows bounded model autonomy while keeping authority in a deterministic
control plane.

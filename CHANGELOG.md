# Changelog

## Unreleased

## [0.1.0] - 2026-08-09

### Product positioning and adoption path

- Reframed T.R.U.S.T. as CI-enforced assurance and policy-as-code for AI
  engineering evidence.
- Moved the concrete pull-request payoff and executable checks ahead of
  governance and standards vocabulary in the README.
- Made the onboarding limitation explicit before adding the locally installable
  existing-repository flow; PyPI publication remains pending.
- Added a public, acceptance-criteria-driven roadmap for `trust init`,
  `trust add`, the GitHub Action, SARIF, editor support, framework examples, OPA
  interoperability, discovery, and reproducible external adoption evidence.

### Existing-repository CLI

- Added the `trust-ai` Python package and `trust` console entry point.
- Added `trust init`, which creates self-contained `.trust/` schema and policy
  files without overwriting local changes.
- Added `trust add <path>`, which detects Python source and matching tests and
  creates a schema-valid draft without fabricating enforced controls.
- Added explicit `draft` lifecycle and `unsupported` control states; active
  manifests still require measured blocking metrics and current evidence.
- Made `trust check` run from an initialized external project root with
  component-level results and remediation for unsupported controls, missing
  evidence, stale hashes, failed evaluations, metric drift, and expired
  exceptions.
- Added external-project end-to-end tests and validated the console entry point
  with a clean wheel-install smoke test.

### Schema 2.0 assurance hardening

- Split declaration and policy validation (`trust lint`) from repository
  evidence verification and executable evaluation (`trust verify`).
- Replaced boolean and prose-only assurance claims with explicit `enforced`,
  `not_applicable`, and `exception` control states.
- Replaced scalar `risk_tier` with reviewed consequence, likelihood, exposure,
  and detectability fields.
- Added suite hashes, shell-free commands, populations, dates, comparators,
  observed values, units, result keys, producing test IDs, and high-risk slice
  requirements.
- Added structured confirmation, payload-bound idempotency,
  transaction/compensation, independent approval, audit, and exception controls.
- Replaced declaration-count coverage with verified control-status coverage.
- Added negative mutation tests and corrected evidence, fallback, total-timeout,
  reference-token, idempotency, and support-answer examples.
- Added a component-scoped threat model and executable metadata-only audit/alert
  sink; undeployed references now declare alerts `not_applicable`.

### Framework

- Repositioned T.R.U.S.T. as a lightweight engineering control framework.
- Replaced immutable-axiom language with durable, change-controlled principles.
- Canonicalized T1, R, U, S, and T2 in `framework/principles.yaml`.
- Replaced product-stage maturity with consequence tiers and authority modes.
- Added the mandatory security, privacy, and compliance overlay.

### Engineering controls

- Added `trust.yaml`, its JSON Schema, risk-tier policy, and dependency-free
  `trust lint`.
- Added coverage reporting, documentation synchronization, link checking, model
  registry validation, a PR template, and GitHub Actions workflow.
- Added evidence labels for operational numeric claims.

### Examples and evidence

- Replaced provider-coupled positive examples with offline executable references.
- Replaced medical triage with support-ticket triage.
- Added deterministic tests, reproducible repository case studies, and explicit
  guarantee/non-guarantee statements.

### Documentation

- Removed duplicate root documentation and stale Q2/2025 links.
- Added a versioned crosswalk to NIST AI RMF, OWASP GenAI, Google SAIF, and
  ISO/IEC 42001 themes.
- Added decision and exception processes.

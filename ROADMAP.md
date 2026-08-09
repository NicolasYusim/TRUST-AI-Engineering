# T.R.U.S.T. roadmap

T.R.U.S.T. is moving from a repository reference implementation to a tool that
an engineer can add to an existing project without learning the full assurance
model first.

This roadmap is ordered by activation value, not by framework completeness. An
item marked **planned** is a direction, not a release commitment. Contributions
should satisfy the acceptance criteria rather than add a command or integration
in name only.

## Now — install, initialize, and fail usefully

### Existing-repository bootstrap — in progress

- [x] Package the CLI so a local checkout is installable with `pipx install .`.
- [x] Add `trust init` to create the minimum project configuration and CI-ready
  directories without copying the T.R.U.S.T. source repository.
- [x] Add `trust add <path>` to create a component manifest from a code path and
  clearly mark evidence that still needs an engineer's decision.
- [x] Make `trust check` run from the target project root.
- [ ] Publish the `trust-ai` package so `pipx install trust-ai` works without a
  source checkout.

**Ready when:** a new project can install, initialize, add one AI component, and
receive a component-level pass/fail result in two minutes from a clean checkout.
The generated manifest must be reviewable and must not claim that a control is
enforced without evidence.

### Actionable check output — implemented

- [x] Report checks by component and control instead of only raw manifest paths.
- [x] Separate verified controls, unsupported claims, stale evidence, and expired
  exceptions.
- [x] End with one unambiguous CI result and the next action for every failure.

**Target experience:**

```text
✓ 3 AI components found
✓ 14 controls verified
✗ payment-agent: irreversible action has no confirmation evidence
✗ support-agent: evaluation result is stale

TRUST check failed
```

Acceptance is covered by end-to-end tests for a generated draft, a passing
external component, and a stale evaluation-suite hash.

### GitHub Action — planned

- Provide a version-pinned action that runs `trust check` on pull requests.
- Cache installation safely and upload a human-readable summary.
- Document least-privilege permissions and fork behavior.

**Ready when:** an existing repository can add one workflow file and receive the
same decision locally and in GitHub Actions.

### SARIF output — planned

- Add a stable rule ID for every check.
- Map component and evidence failures to precise repository locations.
- Upload results to GitHub code scanning in the reference Action.

**Ready when:** CLI text and SARIF report the same findings and regression tests
cover paths, severity, fingerprints, and rule IDs.

### Editor schema support — planned

- Publish a stable schema URL for `trust.yaml`.
- Document VS Code YAML schema association and validate completion behavior.

**Ready when:** a developer gets field completion and inline validation in a
new repository without copying the schema locally.

## Next — prove value outside this repository

### External project evidence — planned

Apply T.R.U.S.T. to at least three projects outside this repository, including
one established open-source AI project. Publish, for each project:

- the reviewed commit and component boundaries;
- declared, verified, unsupported, and excepted control counts;
- the exact findings that changed an engineering decision;
- the committed manifest, evidence, and reproducible command; and
- what the assessment does not prove.

**Ready when:** another engineer can reproduce each result from the named commit.
Until then, the current case studies remain synthetic repository fixtures, not
external adoption evidence.

### Framework examples — planned

- OpenAI Agents SDK example.
- LangGraph example.
- Model Context Protocol (MCP) example.

Each example must include a safe path, a failing control, executable evaluation
evidence, and a statement of scope. A code sample without a reproducible gate is
not complete.

### OPA interoperability — planned

- Define a stable JSON decision document for resolved T.R.U.S.T. controls.
- Provide an example that consumes the decision in Open Policy Agent.
- Keep evidence verification in T.R.U.S.T.; do not represent declaration-only
  input as a verified OPA decision.

**Ready when:** the same verified result can gate a local command and an OPA
policy without duplicating assurance semantics.

## Later — reduce manual inventory work

### AI component discovery — planned

- Detect likely model, agent, retrieval, and tool-use boundaries in common
  project layouts.
- Show candidates before writing files.
- Preserve an explicit engineer decision about component scope and authority.

**Ready when:** discovery reduces setup work on the external project set without
silently excluding components or turning heuristics into assurance claims.

## Contributing

Start with the first incomplete milestone whose acceptance criteria match the
problem you want to solve. Follow the repository's
[contribution rules](CONTRIBUTING.md), include positive and negative tests, and
keep every enforced claim tied to current evidence.

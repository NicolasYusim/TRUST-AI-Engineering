# Contributing to T.R.U.S.T.

T.R.U.S.T. should make AI assurance claims more precise and verifiable, not
make manifests or documentation longer for their own sake. Contributions must
preserve the framework's evidence-first, risk-proportional, and
anti-overclaiming character.

## Before making a change

1. Identify the one repository layer that owns the rule or claim.
2. Describe a realistic component or request that the change should affect.
3. Describe a nearby case that it should not affect.
4. Name the observable failure mode or unsupported claim the change prevents.
5. Prefer a concise, executable rule over a broad catalog of advice.

Do not copy a normative rule into several layers. Keep one machine-readable
source of truth and make other documents explain or reference it.

## Ownership boundaries

| Concern | Owner |
| --- | --- |
| Canonical principle names, statements, and review questions | `framework/principles.yaml` |
| Consequence- and authority-based requirements | `policies/risk-tiers.yaml` |
| Component and exception document shape | `schema/` |
| Component-specific declarations and evidence links | `components/*/trust.yaml` |
| Lint, verification, evidence, and coverage semantics | `trustlib/` and `trust` |
| Executable behavior and regression protection | `tests/`, `evals/`, and result artifacts |
| Reference implementation patterns and counterexamples | `examples/` |
| Dated provider and model facts | `registry/models.yaml` |
| Current guidance, overlays, mappings, and runbooks | `docs/` |
| Scoped, temporary control exceptions | `exceptions/` |

When a symptom touches several layers, change the owner of the root cause and
update dependent artifacts only as needed to keep them synchronized.

## Editing rules

- Preserve the dependency-free Python runtime and the strict JSON-compatible
  subset of YAML used by normative repository files.
- Require exact repository or runtime evidence for enforced control claims.
- Use `unsupported` only in generated `lifecycle: draft` manifests to expose an
  incomplete evidence decision. Active manifests and passing checks must resolve
  the control as `enforced`, a policy-permitted `not_applicable`, or an approved
  `exception`.
- Keep declarations, policy, and verification separate: a manifest states a
  claim, policy determines what is required, and verification proves the cited
  evidence is current.
- Distinguish `measured`, `documented_external`, and `recommended_default`
  numbers and include the metadata required by the selected evidence basis.
- State what an example or measurement does not prove. Never generalize an
  offline fixture, reference implementation, or repository test into a
  production assurance claim.
- Include positive and negative tests for new validation behavior. Reject
  nearby false positives, permitted `not_applicable` states, and needless
  migrations explicitly.
- Treat schema, canonical principle, control path, and policy changes as
  compatibility changes. Document their impact and provide a migration path
  when existing consumers or manifests are affected.
- Regenerate `reports/coverage.md` with `./trust coverage`; do not edit the
  generated snapshot by hand.
- Keep local links repository-relative and resolvable by `./trust docs`.
- Do not combine a control change with unrelated wording, metadata, generated
  output, or repository-wide formatting.

## Change-specific requirements

### Canonical principles

Changing a canonical name, statement, or review question requires the decision
record described in
[`docs/decisions-and-exceptions.md`](docs/decisions-and-exceptions.md). Update
`framework/principles.yaml`, synchronized documentation, and `CHANGELOG.md` in
the same change.

### Schemas, policy, and verification

- Add a valid example for the intended path.
- Add a focused invalid mutation for the failure being prevented.
- Test the nearest valid boundary so the new rule does not reject it.
- Update affected manifests and documentation deliberately; do not weaken
  evidence merely to make the suite pass.
- Explain compatibility impact and rejected alternatives in the pull request.

### Component evidence

- Link controls to the implementation, tests, result artifacts, or operational
  documents that actually support the claim.
- Keep suite hashes, result keys, observed values, test IDs, populations, and
  evaluation dates consistent.
- Use `exception` rather than `enforced` when evidence is incomplete and
  `not_applicable` rather than empty evidence when policy permits it.
- Do not add secrets, personal data, raw sensitive prompts, or production
  payloads as evidence fixtures.

### Exceptions and dated facts

Exceptions must be scoped, independently approved, evidenced, time-bounded,
and linked from the affected manifest. Registry and external-framework facts
must include their source, verification date, status, owner, and applicable
version or scope.

## Test the behavior

Exercise at least these cases when they are relevant to the change:

1. A valid declaration and verified evidence path.
2. The exact invalid mutation the rule should reject.
3. A nearby valid case that must continue to pass.
4. Allowed and forbidden `not_applicable` states.
5. A valid exception and an expired, unapproved, or mis-scoped exception.
6. Stale hashes, mismatched result values or test IDs, and missing evidence.
7. Missing tools, external data, or execution evidence without fabricated
   success.

Tests should receive raw manifests, diffs, fixtures, artifacts, or command
results—not the expected findings encoded as input.

## Validate the repository

Run the complete repository gate:

```bash
./trust check
```

Run the test suite directly when validation or runtime behavior changed:

```bash
python3 -m unittest discover -s tests -v
```

If coverage changed, regenerate and then verify the checked-in snapshot:

```bash
./trust coverage > reports/coverage.md
./trust coverage --check reports/coverage.md
```

## Pull requests

Keep each pull request focused on one assurance or decision-quality
improvement. Explain:

- the claim, behavior, or failure mode being improved;
- the repository layer that owns it;
- the components, prompts, fixtures, or artifacts used for testing;
- compatibility and migration impact;
- rejected alternatives;
- validation results.

Reviewers should be able to trace every new enforced claim to current evidence
and every normative change to an executable check or an explicit decision.

# Evidence labels for operational numbers

Every operational numeric claim or setting must declare a basis. This includes
thresholds, timeouts, rates, budgets, sample sizes, cost claims, and claimed
improvements.

| Label | Meaning | Required metadata |
|---|---|---|
| `measured` | Reproduced on a declared suite or observed population | Evidence path, population/suite, date |
| `illustrative` | Demonstrates mechanics only | Rationale that it is not a recommendation |
| `recommended_default` | Starting value pending local calibration | Rationale, owner, review condition |
| `externally_sourced` | Taken from a dated primary source | Source URL and verification date |

## Manifest representation

```json
{
  "value": 2500,
  "unit": "ms",
  "basis": "recommended_default",
  "rationale": "Starting SLO for the reference component; calibrate from user research."
}
```

A blocking metric uses the same convention:

```json
{
  "comparator": ">=",
  "threshold": 0.92,
  "observed": 0.94,
  "unit": "ratio",
  "basis": "measured",
  "evidence": "case-studies/results/support-answer-generator.json",
  "result_key": "metrics.groundedness",
  "test_ids": ["test_groundedness_gate"]
}
```

Blocking metrics must be `measured`; illustrative thresholds cannot pass a gate.
The suite declares a repository path, SHA-256 digest, shell-free command,
expected test IDs, population, evaluation date, and result artifact. Every metric
and slice names its producing tests; the artifact independently maps each
`result_key` to the same test IDs. `./trust verify` checks the hash and artifact
metadata, verifies that mapping, resolves `result_key`, compares it with
`observed`, evaluates the comparator, runs each unique suite command, and rejects
a gate when a declared test ID was not reported by that successful run.

For other numeric settings, the schema and `./trust lint` require evidence,
population, and date for `measured`; owner and review condition for
`recommended_default`; and a dated HTTPS source for `externally_sourced`.

## Scope

Evidence labels apply to operational recommendations and performance claims.
They are not required for dates, versions, identifiers, list numbering, or
literal fixture values that are not presented as transferable claims.

# Decisions and exceptions

## Durable-principle decision

Changing a canonical name, statement, or review question requires:

- problem and evidence;
- affected controls and compatibility impact;
- alternatives considered;
- approval and effective date;
- migration plan for docs, specs, and tooling.

Record the change in `CHANGELOG.md` and update
`framework/principles.yaml`. Documentation synchronization tests must pass.

## Control exception

Create one `EXC-YYYY-NNN.yaml` file under
[`../exceptions/`](../exceptions/) using the strict schema and template there.
Set the affected control to `status: exception`, reference the same ID from the
control and top-level manifest list, and provide:

- component and control;
- scoped reason;
- risk and consequence;
- compensating control;
- owner and approver;
- creation and expiry dates;
- removal or review plan.

Exceptions do not change the canonical framework and may not be open-ended.
The owner and approver must be independent. `trust lint` validates the record
and linkage; `trust verify` checks evidence, expiry, and the maximum lifetime for
the component's consequence tier.

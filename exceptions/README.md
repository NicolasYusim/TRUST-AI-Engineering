# Control exceptions

Create one strict JSON-compatible YAML file named `EXC-YYYY-NNN.yaml`:

```json
{
  "schema_version": "1.0",
  "id": "EXC-2026-001",
  "component": "component-name",
  "control": "section.control_name",
  "owner": "accountable-team",
  "approver": "independent-risk-owner",
  "created": "2026-07-27",
  "expires": "2026-08-26",
  "risk": "Concrete consequence accepted for the bounded exception period.",
  "reason": "Why the required control cannot yet be enforced.",
  "compensating_control": "The temporary control that reduces the accepted risk.",
  "review_plan": "Removal owner, milestone, and review trigger.",
  "evidence": ["tests/test_framework.py"]
}
```

The component control uses `status: exception`, names the same `exception_id`,
and lists the ID in its top-level `exceptions` array.

`trust lint` validates schema, component/control linkage, and file presence.
`trust verify` requires independent approval, repository evidence, a future
expiry, and a lifetime no longer than the component tier permits.

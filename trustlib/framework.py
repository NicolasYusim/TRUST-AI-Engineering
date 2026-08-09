from __future__ import annotations

import datetime as dt
import math
import operator
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from .schema import (
    dotted_get,
    load_json_yaml,
    relative_label,
    repository_file,
    sha256_file,
    validate_schema,
)


ROOT = Path(__file__).resolve().parents[1]
TODAY = dt.date.today

PRINCIPLE_DOCS = {
    "T1": [
        "README.md",
        "PRINCIPLES.md",
        "principles/T1-traceability.md",
        "code-review/traceability-checklist.md",
    ],
    "R": [
        "README.md",
        "PRINCIPLES.md",
        "principles/R-resilience.md",
        "code-review/resilience-checklist.md",
    ],
    "U": [
        "README.md",
        "PRINCIPLES.md",
        "principles/U-unit-economics.md",
        "code-review/unit-economics-checklist.md",
    ],
    "S": [
        "README.md",
        "PRINCIPLES.md",
        "principles/S-state-structure.md",
        "code-review/state-structure-checklist.md",
    ],
    "T2": [
        "README.md",
        "PRINCIPLES.md",
        "principles/T2-testability.md",
        "code-review/testability-checklist.md",
    ],
}

PRINCIPLE_CONTROLS = {
    "T1": (
        "traceability.prompt_versioning",
        "traceability.input_provenance",
        "traceability.source_provenance",
        "traceability.tool_event_logging",
    ),
    "R": (
        "resilience.bounded_recovery",
        "resilience.service_objective",
    ),
    "U": (
        "utility.expected_benefit",
        "utility.resource_bounds",
    ),
    "S": (
        "authority.confirmation",
        "authority.idempotency",
        "authority.transaction_or_compensation",
        "authority.independent_approval",
        "security.sandbox",
    ),
    "T2": (
        "evaluation.uncertainty_control",
        "evaluation.slice_analysis",
        "evaluation.oversight",
    ),
}

OVERLAY_CONTROLS = (
    "security.threat_model",
    "security.secrets",
    "security.audit",
    "operations.alerts",
    "operations.runbook",
)

ALL_CONTROL_PATHS = tuple(
    dict.fromkeys(
        control
        for controls in (*PRINCIPLE_CONTROLS.values(), OVERLAY_CONTROLS)
        for control in controls
    )
)

SETTING_UNITS = {
    "data.retention_days": "days",
    "authority.max_effects": "effects",
    "resilience.timeout_ms": "ms",
    "resilience.max_attempts": "attempts",
    "utility.latency_slo_ms": "ms",
    "utility.monthly_budget_usd": "USD/month",
    "utility.output_token_limit": "reference_tokens",
}

CONTROL_DOCUMENT_PREFIXES = {
    "security.threat_model": "docs/threat-models/",
    "operations.runbook": "docs/runbooks/",
}

COMPARATORS = {
    ">=": operator.ge,
    ">": operator.gt,
    "<=": operator.le,
    "<": operator.lt,
    "==": lambda left, right: math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-12),
}


def _load_repository_specs(
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    specs_root = root
    if not all((root / relative).is_file() for relative in (
        "schema/trust.schema.json",
        "schema/exception.schema.json",
        "policies/risk-tiers.yaml",
    )):
        specs_root = root / ".trust"
    schema = load_json_yaml(specs_root / "schema/trust.schema.json", root)
    policy = load_json_yaml(specs_root / "policies/risk-tiers.yaml", root)
    exception_schema = load_json_yaml(
        specs_root / "schema/exception.schema.json",
        root,
    )
    return schema, policy, exception_schema


def _date_not_future(raw: str, path: str) -> list[str]:
    try:
        value = dt.date.fromisoformat(raw)
    except (TypeError, ValueError):
        return [f"{path}: expected an ISO date"]
    if value > TODAY():
        return [f"{path}: date is in the future"]
    return []


def _control_entries(
    manifest: dict[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    entries: list[tuple[str, dict[str, Any]]] = []
    for path in ALL_CONTROL_PATHS:
        try:
            value = dotted_get(manifest, path)
        except KeyError:
            continue
        if isinstance(value, dict):
            entries.append((path, value))
    return entries


def _control_semantic_errors(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    declared_exceptions = set(manifest.get("exceptions", []))
    referenced_exceptions: set[str] = set()

    for path, control in _control_entries(manifest):
        status = control.get("status")
        evidence = control.get("evidence", [])
        exception_id = control.get("exception_id")
        if status == "enforced":
            if not evidence:
                errors.append(f"$.{path}: enforced control requires evidence")
            if exception_id:
                errors.append(
                    f"$.{path}: enforced control must not declare exception_id"
                )
        elif status == "not_applicable":
            if evidence:
                errors.append(
                    f"$.{path}: not_applicable control must not claim evidence"
                )
            if exception_id:
                errors.append(
                    f"$.{path}: not_applicable control must not declare exception_id"
                )
        elif status == "unsupported":
            if evidence:
                errors.append(
                    f"$.{path}: unsupported control must not claim evidence"
                )
            if exception_id:
                errors.append(
                    f"$.{path}: unsupported control must not declare exception_id"
                )
            errors.append(
                f"$.{path}.status: unsupported control requires evidence, "
                "a permitted not_applicable rationale, or an approved exception"
            )
        elif status == "exception":
            if not exception_id:
                errors.append(f"$.{path}: exception status requires exception_id")
            else:
                referenced_exceptions.add(exception_id)
                if exception_id not in declared_exceptions:
                    errors.append(
                        f"$.{path}: exception_id {exception_id!r} is not listed in $.exceptions"
                    )

    for exception_id in sorted(declared_exceptions - referenced_exceptions):
        errors.append(
            f"$.exceptions: {exception_id!r} is not referenced by a control"
        )
    return errors


def _number_setting_errors(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for path, expected_unit in SETTING_UNITS.items():
        try:
            setting = dotted_get(manifest, path)
        except KeyError:
            continue
        if not isinstance(setting, dict):
            continue
        if setting.get("unit") != expected_unit:
            errors.append(
                f"$.{path}.unit: expected {expected_unit!r}, got {setting.get('unit')!r}"
            )

        basis = setting.get("basis")
        if basis == "measured":
            for field in ("evidence", "population", "evaluated_at"):
                if not setting.get(field):
                    errors.append(
                        f"$.{path}: measured setting requires {field}"
                    )
            if setting.get("evaluated_at"):
                errors.extend(
                    _date_not_future(
                        setting["evaluated_at"],
                        f"$.{path}.evaluated_at",
                    )
                )
        elif basis == "recommended_default":
            for field in ("owner", "review_condition"):
                if not setting.get(field):
                    errors.append(
                        f"$.{path}: recommended_default setting requires {field}"
                    )
        elif basis == "externally_sourced":
            if not str(setting.get("source", "")).startswith("https://"):
                errors.append(
                    f"$.{path}: externally_sourced setting requires an HTTPS source"
                )
            if not setting.get("verified_at"):
                errors.append(
                    f"$.{path}: externally_sourced setting requires verified_at"
                )
            else:
                errors.extend(
                    _date_not_future(
                        setting["verified_at"],
                        f"$.{path}.verified_at",
                    )
                )

    for path in (
        "resilience.timeout_ms",
        "resilience.max_attempts",
        "utility.latency_slo_ms",
        "utility.output_token_limit",
    ):
        try:
            value = dotted_get(manifest, f"{path}.value")
        except KeyError:
            continue
        if isinstance(value, (int, float)) and value <= 0:
            errors.append(f"$.{path}.value: must be greater than zero")

    for path in ("authority.max_effects", "resilience.max_attempts"):
        try:
            value = dotted_get(manifest, f"{path}.value")
        except KeyError:
            continue
        if not isinstance(value, int) or isinstance(value, bool):
            errors.append(f"$.{path}.value: must be an integer")
    return errors


def _risk_and_authority_errors(
    manifest: dict[str, Any],
    policy: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    try:
        tier_name = dotted_get(manifest, "risk.consequence_tier")
        authority_mode = dotted_get(manifest, "authority.mode")
    except KeyError:
        return errors

    tier = policy.get("tiers", {}).get(tier_name, {})
    allowed_modes = tier.get("allowed_authority_modes", [])
    if allowed_modes and authority_mode not in allowed_modes:
        errors.append(
            f"$.authority.mode: {authority_mode!r} is not allowed for "
            f"consequence tier {tier_name!r}"
        )

    required_controls = list(policy.get("common_required_controls", []))
    required_controls.extend(tier.get("required_controls", []))
    authority_policy = policy.get("authority_controls", {}).get(authority_mode, {})
    required_controls.extend(authority_policy.get("required_controls", []))
    for control_path in dict.fromkeys(required_controls):
        try:
            status = dotted_get(manifest, f"{control_path}.status")
        except KeyError:
            errors.append(f"$.{control_path}: required control is missing")
            continue
        if status not in {"enforced", "exception"}:
            errors.append(
                f"$.{control_path}.status: tier/policy requires enforced or exception"
            )

    required_statuses = authority_policy.get("required_statuses", {})
    for control_path, expected in required_statuses.items():
        try:
            actual = dotted_get(manifest, f"{control_path}.status")
        except KeyError:
            errors.append(f"$.{control_path}: required control is missing")
            continue
        if actual != expected:
            errors.append(
                f"$.{control_path}.status: expected {expected!r}, got {actual!r}"
            )

    required_values = dict(tier.get("required_values", {}))
    required_values.update(authority_policy.get("required_values", {}))
    for path, expected in required_values.items():
        try:
            actual = dotted_get(manifest, path)
        except KeyError:
            errors.append(f"$.{path}: policy requires {expected!r}")
            continue
        if actual != expected:
            errors.append(
                f"$.{path}: policy requires {expected!r}, got {actual!r}"
            )

    slices = manifest.get("evaluation", {}).get("slices", [])
    minimum_slices = tier.get("minimum_slices", 0)
    if isinstance(slices, list) and len(slices) < minimum_slices:
        errors.append(
            f"$.evaluation.slices: tier {tier_name!r} requires at least "
            f"{minimum_slices} slice metric(s)"
        )

    tools = manifest.get("authority", {}).get("allowed_tools", [])
    resources = manifest.get("authority", {}).get("allowed_resources", [])
    destinations = manifest.get("authority", {}).get(
        "allowed_network_destinations", []
    )
    max_effects = (
        manifest.get("authority", {}).get("max_effects", {}).get("value")
    )
    if authority_mode == "advisory":
        if tools or resources or destinations:
            errors.append(
                "$.authority: advisory components cannot declare tools, resources, "
                "or network destinations"
            )
        if max_effects != 0:
            errors.append("$.authority.max_effects.value: advisory mode requires 0")
    elif authority_mode == "read_only":
        if not tools or not resources:
            errors.append(
                "$.authority: read_only mode requires scoped tools and resources"
            )
        if max_effects != 0:
            errors.append("$.authority.max_effects.value: read_only mode requires 0")
    else:
        if not tools or not resources:
            errors.append(
                "$.authority: write modes require scoped tools and resources"
            )
        if not isinstance(max_effects, (int, float)) or max_effects < 1:
            errors.append("$.authority.max_effects.value: write modes require >= 1")

    confirmation = manifest.get("authority", {}).get("confirmation", {})
    idempotency = manifest.get("authority", {}).get("idempotency", {})
    transaction = manifest.get("authority", {}).get(
        "transaction_or_compensation",
        {},
    )
    independent = manifest.get("authority", {}).get(
        "independent_approval",
        {},
    )
    if authority_mode in {"advisory", "read_only"}:
        expected_inactive = [
            (
                confirmation.get("identity_source"),
                "not_applicable",
                "$.authority.confirmation.identity_source",
            ),
            (
                confirmation.get("bound_to_plan"),
                False,
                "$.authority.confirmation.bound_to_plan",
            ),
            (
                idempotency.get("key_scope"),
                "not_applicable",
                "$.authority.idempotency.key_scope",
            ),
            (
                idempotency.get("payload_binding"),
                False,
                "$.authority.idempotency.payload_binding",
            ),
            (
                transaction.get("strategy"),
                "not_applicable",
                "$.authority.transaction_or_compensation.strategy",
            ),
        ]
        if tier_name != "critical":
            expected_inactive.append(
                (
                    independent.get("identity_source"),
                    "not_applicable",
                    "$.authority.independent_approval.identity_source",
                )
            )
            expected_inactive.append(
                (
                    independent.get("independent_from_owner"),
                    False,
                    "$.authority.independent_approval.independent_from_owner",
                )
            )
        for actual, expected, field in expected_inactive:
            if actual != expected:
                errors.append(f"{field}: expected {expected!r}, got {actual!r}")
    else:
        if confirmation.get("bound_to_plan") is not True:
            errors.append(
                "$.authority.confirmation.bound_to_plan: write authority "
                "requires action-bound confirmation"
            )
        if confirmation.get("identity_source") == "not_applicable":
            errors.append(
                "$.authority.confirmation.identity_source: write authority "
                "requires an authenticated approval identity"
            )
        if idempotency.get("payload_binding") is not True:
            errors.append(
                "$.authority.idempotency.payload_binding: write authority "
                "requires payload-bound keys"
            )
        if idempotency.get("key_scope") == "not_applicable":
            errors.append(
                "$.authority.idempotency.key_scope: write authority requires "
                "a concrete key scope"
            )
        if transaction.get("strategy") not in {"transaction", "compensation"}:
            errors.append(
                "$.authority.transaction_or_compensation.strategy: write "
                "authority requires transaction or compensation"
            )
    if authority_mode == "irreversible_action" or tier_name == "critical":
        if independent.get("independent_from_owner") is not True:
            errors.append(
                "$.authority.independent_approval.independent_from_owner: "
                "critical or irreversible actions require independent approval"
            )
        if independent.get("identity_source") == "not_applicable":
            errors.append(
                "$.authority.independent_approval.identity_source: critical "
                "or irreversible actions require a qualified identity source"
            )

    if tools:
        try:
            logging_status = dotted_get(
                manifest,
                "traceability.tool_event_logging.status",
            )
        except KeyError:
            logging_status = None
        if logging_status not in {"enforced", "exception"}:
            errors.append(
                "$.traceability.tool_event_logging.status: tools require enforced "
                "logging or a documented exception"
            )

    return errors


def _traceability_consistency_errors(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    pairs = (
        (
            "traceability.input_provenance",
            "traceability.input_provenance_method",
        ),
        (
            "traceability.source_provenance",
            "traceability.source_provenance_method",
        ),
    )
    for control_path, method_path in pairs:
        try:
            status = dotted_get(manifest, f"{control_path}.status")
            method = dotted_get(manifest, method_path)
        except KeyError:
            continue
        if status == "not_applicable" and method != "not_applicable":
            errors.append(
                f"$.{method_path}: not_applicable control requires not_applicable method"
            )
        if status != "not_applicable" and method == "not_applicable":
            errors.append(
                f"$.{method_path}: active control requires a concrete method"
            )
    return errors


def _evaluation_contract_errors(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    lifecycle = manifest.get("lifecycle", "active")
    if lifecycle == "draft":
        errors.append(
            "$.lifecycle: draft manifest cannot pass the repository gate; "
            "review the evidence and set lifecycle to active"
        )
    evaluation = manifest.get("evaluation", {})
    suite = evaluation.get("suite", {})
    suite_path = suite.get("path", "")
    if suite_path and not suite_path.startswith(("tests/", "evals/")):
        errors.append(
            "$.evaluation.suite.path: suite must live under tests/ or evals/"
        )
    if suite_path and Path(suite_path).suffix not in {".py", ".json", ".jsonl"}:
        errors.append(
            "$.evaluation.suite.path: unsupported executable suite type"
        )
    evidence_path = suite.get("evidence", "")
    if evidence_path and (
        not evidence_path.startswith("case-studies/results/")
        or Path(evidence_path).suffix != ".json"
    ):
        errors.append(
            "$.evaluation.suite.evidence: result must be a JSON artifact under "
            "case-studies/results/"
        )
    command = suite.get("command", [])
    if command and command[:3] != ["python3", "-m", "unittest"]:
        errors.append(
            "$.evaluation.suite.command: only shell-free `python3 -m unittest` "
            "commands are accepted"
        )
    if "-c" in command:
        errors.append("$.evaluation.suite.command: inline Python is not allowed")
    suite_test_ids = set(suite.get("test_ids", []))

    metrics = evaluation.get("blocking_metrics", {})
    if not metrics and lifecycle != "draft":
        errors.append(
            "$.evaluation.blocking_metrics: active manifests require at least "
            "one measured blocking metric"
        )
    for metric_id, metric in metrics.items() if isinstance(metrics, dict) else ():
        if metric.get("basis") != "measured":
            errors.append(
                f"$.evaluation.blocking_metrics.{metric_id}.basis: blocking "
                "metrics must be measured"
            )
        if metric.get("evidence") != evidence_path:
            errors.append(
                f"$.evaluation.blocking_metrics.{metric_id}.evidence: must match "
                "$.evaluation.suite.evidence"
            )
        unknown_test_ids = set(metric.get("test_ids", [])) - suite_test_ids
        if unknown_test_ids:
            errors.append(
                f"$.evaluation.blocking_metrics.{metric_id}.test_ids: tests are "
                f"not declared by the suite: {sorted(unknown_test_ids)!r}"
            )
        comparator_name = metric.get("comparator")
        observed = metric.get("observed")
        threshold = metric.get("threshold")
        if (
            comparator_name in COMPARATORS
            and isinstance(observed, (int, float))
            and not isinstance(observed, bool)
            and isinstance(threshold, (int, float))
            and not isinstance(threshold, bool)
            and not COMPARATORS[comparator_name](observed, threshold)
        ):
            errors.append(
                f"$.evaluation.blocking_metrics.{metric_id}: observed "
                f"{observed!r} does not satisfy {comparator_name} {threshold!r}"
            )

    for index, slice_metric in enumerate(evaluation.get("slices", [])):
        if slice_metric.get("evidence") != evidence_path:
            errors.append(
                f"$.evaluation.slices[{index}].evidence: must match "
                "$.evaluation.suite.evidence"
            )
        unknown_test_ids = set(slice_metric.get("test_ids", [])) - suite_test_ids
        if unknown_test_ids:
            errors.append(
                f"$.evaluation.slices[{index}].test_ids: tests are not declared "
                f"by the suite: {sorted(unknown_test_ids)!r}"
            )
        comparator_name = slice_metric.get("comparator")
        observed = slice_metric.get("observed")
        threshold = slice_metric.get("threshold")
        if (
            comparator_name in COMPARATORS
            and isinstance(observed, (int, float))
            and not isinstance(observed, bool)
            and isinstance(threshold, (int, float))
            and not isinstance(threshold, bool)
            and not COMPARATORS[comparator_name](observed, threshold)
        ):
            errors.append(
                f"$.evaluation.slices[{index}]: observed {observed!r} does not "
                f"satisfy {comparator_name} {threshold!r}"
            )
    return errors


def _exception_declaration_errors(
    manifest: dict[str, Any],
    root: Path,
    exception_schema: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    component = manifest.get("component")
    controls_by_exception = {
        control.get("exception_id"): path
        for path, control in _control_entries(manifest)
        if control.get("status") == "exception"
    }
    for exception_id in manifest.get("exceptions", []):
        path, exception_label = _exception_path(root, exception_id)
        if not path.exists():
            errors.append(
                f"$.exceptions: exception file does not exist: "
                f"{exception_label}"
            )
            continue
        try:
            exception = load_json_yaml(path, root)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        errors.extend(
            f"{exception_label}: {error}"
            for error in validate_schema(
                exception,
                exception_schema,
                exception_schema,
            )
        )
        if not isinstance(exception, dict):
            continue
        if exception.get("id") != exception_id:
            errors.append(
                f"{exception_label}: $.id must equal {exception_id!r}"
            )
        if exception.get("component") != component:
            errors.append(
                f"{exception_label}: $.component must equal "
                f"{component!r}"
            )
        expected_control = controls_by_exception.get(exception_id)
        if exception.get("control") != expected_control:
            errors.append(
                f"{exception_label}: $.control must equal "
                f"{expected_control!r}"
            )
    return errors


def lint_manifest(
    path: Path,
    schema: dict[str, Any],
    policy: dict[str, Any],
    *,
    root: Path = ROOT,
    exception_schema: dict[str, Any] | None = None,
) -> list[str]:
    try:
        manifest = load_json_yaml(path, root)
    except ValueError as exc:
        return [str(exc)]

    label = relative_label(path, root)
    errors = [
        f"{label}: {error}"
        for error in validate_schema(manifest, schema, schema)
    ]
    if not isinstance(manifest, dict):
        return errors
    if errors:
        return errors

    if manifest.get("component") != path.parent.name:
        errors.append(
            f"{label}: $.component must match directory name {path.parent.name!r}"
        )

    semantic_errors: list[str] = []
    semantic_errors.extend(_control_semantic_errors(manifest))
    semantic_errors.extend(_number_setting_errors(manifest))
    semantic_errors.extend(_risk_and_authority_errors(manifest, policy))
    semantic_errors.extend(_traceability_consistency_errors(manifest))
    semantic_errors.extend(_evaluation_contract_errors(manifest))
    semantic_errors.extend(
        _date_not_future(
            manifest.get("risk", {}).get("reviewed_at", ""),
            "$.risk.reviewed_at",
        )
    )
    if exception_schema is None:
        try:
            _, _, exception_schema = _load_repository_specs(root)
        except ValueError as exc:
            semantic_errors.append(str(exc))
            exception_schema = {}
    if exception_schema:
        semantic_errors.extend(
            _exception_declaration_errors(
                manifest,
                root,
                exception_schema,
            )
        )
    errors.extend(f"{label}: {error}" for error in semantic_errors)
    return errors


def manifest_paths(root: Path = ROOT) -> list[Path]:
    if (root / ".trust/config.json").is_file():
        return sorted(root.glob(".trust/components/*/trust.yaml"))
    return sorted(root.glob("components/*/trust.yaml"))


def _exception_path(root: Path, exception_id: str) -> tuple[Path, str]:
    external = root / ".trust/exceptions" / f"{exception_id}.yaml"
    repository = root / "exceptions" / f"{exception_id}.yaml"
    path = external if (root / ".trust/config.json").is_file() else repository
    return path, relative_label(path, root)


def _selected_manifest_paths(
    paths: list[str] | None,
    root: Path,
) -> tuple[list[Path], list[str]]:
    if not paths:
        return manifest_paths(root), []
    selected: list[Path] = []
    errors: list[str] = []
    for raw in paths:
        candidate = Path(raw)
        if candidate.is_absolute() or ".." in candidate.parts:
            errors.append(f"manifest path must stay inside the repository: {raw}")
            continue
        selected.append(root / candidate)
    return selected, errors


def run_lint(
    paths: list[str] | None = None,
    *,
    root: Path = ROOT,
) -> tuple[int, list[str]]:
    try:
        schema, policy, exception_schema = _load_repository_specs(root)
    except ValueError as exc:
        return 0, [str(exc)]
    selected, errors = _selected_manifest_paths(paths, root)
    for path in selected:
        errors.extend(
            lint_manifest(
                path,
                schema,
                policy,
                root=root,
                exception_schema=exception_schema,
            )
        )
    if not selected:
        errors.append("no component manifests found")
    return len(selected), errors


def _path_errors(root: Path, relative: str, label: str) -> tuple[Path | None, list[str]]:
    path, error = repository_file(root, relative)
    if error:
        return None, [f"{label}: {error}: {relative}"]
    return path, []


def _artifact_result(
    artifact: dict[str, Any],
    result_key: str,
) -> tuple[Any, str | None]:
    try:
        return dotted_get(artifact, result_key), None
    except KeyError:
        return None, f"result_key {result_key!r} does not exist in evidence artifact"


def _verify_evaluation(
    manifest: dict[str, Any],
    root: Path,
    label: str,
) -> tuple[list[str], tuple[str, ...] | None]:
    errors: list[str] = []
    evaluation = manifest["evaluation"]
    suite = evaluation["suite"]

    suite_path, path_errors = _path_errors(
        root,
        suite["path"],
        f"{label}: $.evaluation.suite.path",
    )
    errors.extend(path_errors)
    if suite_path is not None:
        actual_hash = sha256_file(suite_path)
        if actual_hash != suite["sha256"]:
            errors.append(
                f"{label}: $.evaluation.suite.sha256: expected "
                f"{suite['sha256']}, got {actual_hash}"
            )

    evidence_path, evidence_errors = _path_errors(
        root,
        suite["evidence"],
        f"{label}: $.evaluation.suite.evidence",
    )
    errors.extend(evidence_errors)
    artifact: dict[str, Any] | None = None
    if evidence_path is not None:
        try:
            loaded = load_json_yaml(evidence_path, root)
        except ValueError as exc:
            errors.append(str(exc))
        else:
            if not isinstance(loaded, dict):
                errors.append(
                    f"{label}: evaluation evidence must be a JSON object"
                )
            else:
                artifact = loaded

    if artifact is not None:
        expected_metadata = {
            "schema_version": "1.0",
            "evaluated_at": suite["evaluated_at"],
            "population": suite["population"],
            "command": suite["command"],
        }
        for field, expected in expected_metadata.items():
            if artifact.get(field) != expected:
                errors.append(
                    f"{label}: {suite['evidence']}: $.{field} must equal "
                    f"{expected!r}"
                )
        artifact_test_ids = artifact.get("test_ids")
        if (
            not isinstance(artifact_test_ids, list)
            or not set(suite["test_ids"]).issubset(artifact_test_ids)
        ):
            errors.append(
                f"{label}: {suite['evidence']}: $.test_ids must contain every "
                "test declared by $.evaluation.suite.test_ids"
            )
        result_tests = artifact.get("result_tests")
        if not isinstance(result_tests, dict):
            errors.append(
                f"{label}: {suite['evidence']}: $.result_tests must map "
                "result keys to their producing tests"
            )
            result_tests = {}
        artifact_suite = artifact.get("suite")
        expected_suite = {
            "path": suite["path"],
            "sha256": suite["sha256"],
        }
        if artifact_suite != expected_suite:
            errors.append(
                f"{label}: {suite['evidence']}: $.suite must equal "
                f"{expected_suite!r}"
            )

        for metric_id, metric in evaluation["blocking_metrics"].items():
            if result_tests.get(metric["result_key"]) != metric["test_ids"]:
                errors.append(
                    f"{label}: $.evaluation.blocking_metrics.{metric_id}.test_ids: "
                    f"must equal {suite['evidence']} result_tests entry for "
                    f"{metric['result_key']!r}"
                )
            result, result_error = _artifact_result(
                artifact,
                metric["result_key"],
            )
            if result_error:
                errors.append(
                    f"{label}: $.evaluation.blocking_metrics.{metric_id}: "
                    f"{result_error}"
                )
                continue
            if (
                not isinstance(result, (int, float))
                or isinstance(result, bool)
                or not math.isfinite(result)
            ):
                errors.append(
                    f"{label}: $.evaluation.blocking_metrics.{metric_id}: "
                    "evidence result must be a finite number"
                )
                continue
            if not math.isclose(
                float(result),
                float(metric["observed"]),
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                errors.append(
                    f"{label}: $.evaluation.blocking_metrics.{metric_id}.observed: "
                    f"declares {metric['observed']!r}, evidence contains {result!r}"
                )

        for index, slice_metric in enumerate(evaluation["slices"]):
            if (
                result_tests.get(slice_metric["result_key"])
                != slice_metric["test_ids"]
            ):
                errors.append(
                    f"{label}: $.evaluation.slices[{index}].test_ids: must equal "
                    f"{suite['evidence']} result_tests entry for "
                    f"{slice_metric['result_key']!r}"
                )
            result, result_error = _artifact_result(
                artifact,
                slice_metric["result_key"],
            )
            if result_error:
                errors.append(
                    f"{label}: $.evaluation.slices[{index}]: {result_error}"
                )
                continue
            if (
                not isinstance(result, (int, float))
                or isinstance(result, bool)
                or not math.isfinite(result)
            ):
                errors.append(
                    f"{label}: $.evaluation.slices[{index}]: evidence result "
                    "must be a finite number"
                )
                continue
            if not math.isclose(
                float(result),
                float(slice_metric["observed"]),
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                errors.append(
                    f"{label}: $.evaluation.slices[{index}].observed: declares "
                    f"{slice_metric['observed']!r}, evidence contains {result!r}"
                )

    return errors, tuple(suite["command"])


def _verify_control_evidence(
    manifest: dict[str, Any],
    root: Path,
    label: str,
) -> list[str]:
    errors: list[str] = []
    implementation = manifest["implementation"]
    linked_paths = set(implementation["code"])
    linked_paths.update(implementation["tests"])
    linked_paths.add(manifest["evaluation"]["suite"]["evidence"])

    for relative in implementation["code"]:
        _, path_errors = _path_errors(
            root,
            relative,
            f"{label}: $.implementation.code",
        )
        errors.extend(path_errors)
        if Path(relative).suffix != ".py":
            errors.append(
                f"{label}: $.implementation.code: expected a Python source file: "
                f"{relative}"
            )
    for relative in implementation["tests"]:
        _, path_errors = _path_errors(
            root,
            relative,
            f"{label}: $.implementation.tests",
        )
        errors.extend(path_errors)
        if not relative.startswith("tests/") or Path(relative).suffix != ".py":
            errors.append(
                f"{label}: $.implementation.tests: expected a Python file under "
                f"tests/: {relative}"
            )

    for control_path, control in _control_entries(manifest):
        if control.get("status") != "enforced":
            continue
        resolved_any = False
        for relative in control["evidence"]:
            _, path_errors = _path_errors(
                root,
                relative,
                f"{label}: $.{control_path}.evidence",
            )
            errors.extend(path_errors)
            if relative in linked_paths:
                resolved_any = True
            document_prefix = CONTROL_DOCUMENT_PREFIXES.get(control_path)
            if document_prefix and relative.startswith(document_prefix):
                resolved_any = True
        if not resolved_any:
            errors.append(
                f"{label}: $.{control_path}.evidence: at least one artifact must "
                "link to implementation.code, implementation.tests, evaluation "
                "evidence, or the control's required document"
            )
    return errors


def _verify_number_evidence(
    manifest: dict[str, Any],
    root: Path,
    label: str,
) -> list[str]:
    errors: list[str] = []
    for path in SETTING_UNITS:
        setting = dotted_get(manifest, path)
        if setting.get("basis") != "measured":
            continue
        _, path_errors = _path_errors(
            root,
            setting["evidence"],
            f"{label}: $.{path}.evidence",
        )
        errors.extend(path_errors)
    return errors


def _verify_exceptions(
    manifest: dict[str, Any],
    policy: dict[str, Any],
    root: Path,
    label: str,
) -> list[str]:
    errors: list[str] = []
    tier_name = manifest["risk"]["consequence_tier"]
    maximum_days = policy["tiers"][tier_name]["maximum_exception_days"]
    for exception_id in manifest["exceptions"]:
        path, _ = _exception_path(root, exception_id)
        try:
            exception = load_json_yaml(path, root)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        try:
            created = dt.date.fromisoformat(exception["created"])
            expires = dt.date.fromisoformat(exception["expires"])
        except (KeyError, TypeError, ValueError):
            continue
        if created > TODAY():
            errors.append(f"{label}: {exception_id}: creation date is in the future")
        if expires <= TODAY():
            errors.append(f"{label}: {exception_id}: exception is expired")
        if expires <= created:
            errors.append(
                f"{label}: {exception_id}: expiry must be after creation"
            )
        if (expires - created).days > maximum_days:
            errors.append(
                f"{label}: {exception_id}: tier {tier_name!r} allows at most "
                f"{maximum_days} exception days"
            )
        if exception.get("owner") == exception.get("approver"):
            errors.append(
                f"{label}: {exception_id}: owner and approver must be independent"
            )
        for relative in exception.get("evidence", []):
            _, path_errors = _path_errors(
                root,
                relative,
                f"{label}: {exception_id}: $.evidence",
            )
            errors.extend(path_errors)
    return errors


def verify_manifest(
    path: Path,
    policy: dict[str, Any],
    *,
    root: Path = ROOT,
) -> tuple[list[str], tuple[str, ...] | None]:
    manifest = load_json_yaml(path, root)
    if not isinstance(manifest, dict):
        return [f"{relative_label(path, root)}: manifest must be an object"], None
    label = relative_label(path, root)
    errors: list[str] = []
    errors.extend(_verify_control_evidence(manifest, root, label))
    errors.extend(_verify_number_evidence(manifest, root, label))
    errors.extend(_verify_exceptions(manifest, policy, root, label))
    evaluation_errors, command = _verify_evaluation(manifest, root, label)
    errors.extend(evaluation_errors)
    return errors, command


def run_verify(
    paths: list[str] | None = None,
    *,
    root: Path = ROOT,
    execute_commands: bool = True,
    skip_lint: bool = False,
) -> tuple[int, int, list[str]]:
    selected, selection_errors = _selected_manifest_paths(paths, root)
    errors = list(selection_errors)
    if not skip_lint:
        _, lint_errors = run_lint(paths, root=root)
        errors.extend(lint_errors)
    if errors:
        return len(selected), 0, errors

    try:
        _, policy, _ = _load_repository_specs(root)
    except ValueError as exc:
        return len(selected), 0, [str(exc)]

    commands: dict[tuple[str, ...], set[str]] = {}
    for path in selected:
        manifest_errors, command = verify_manifest(path, policy, root=root)
        errors.extend(manifest_errors)
        if command is not None:
            manifest = load_json_yaml(path, root)
            commands.setdefault(command, set()).update(
                manifest["evaluation"]["suite"]["test_ids"]
            )

    commands_run = 0
    if execute_commands and not errors:
        for command, expected_test_ids in sorted(commands.items()):
            try:
                result = subprocess.run(
                    list(command),
                    cwd=root,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            except subprocess.TimeoutExpired:
                errors.append(
                    f"evaluation command timed out after 60s: {list(command)!r}"
                )
                continue
            commands_run += 1
            if result.returncode != 0:
                detail = (result.stderr or result.stdout).strip()
                errors.append(
                    f"evaluation command failed ({result.returncode}): "
                    f"{list(command)!r}: {detail}"
                )
                continue
            output = f"{result.stdout}\n{result.stderr}"
            for test_id in sorted(expected_test_ids):
                if re.search(rf"\b{re.escape(test_id)}\b", output) is None:
                    errors.append(
                        f"evaluation command did not report required test "
                        f"{test_id!r}: {list(command)!r}"
                    )
    return len(selected), commands_run, errors


def registry_errors(root: Path = ROOT) -> list[str]:
    path = root / "registry/models.yaml"
    try:
        registry = load_json_yaml(path, root)
    except ValueError as exc:
        return [str(exc)]
    if not isinstance(registry, dict):
        return ["registry/models.yaml: registry must be an object"]
    models = registry.get("models")
    if not isinstance(models, list) or not models:
        return ["registry/models.yaml: no model entries"]

    errors: list[str] = []
    for index, entry in enumerate(models):
        prefix = f"registry/models.yaml: $.models[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{prefix}: entry must be an object")
            continue
        for key in ("model", "provider", "verified_at", "source", "status", "owner"):
            if not entry.get(key):
                errors.append(f"{prefix}: missing {key}")
        verified_raw = entry.get("verified_at")
        try:
            verified = dt.date.fromisoformat(verified_raw)
            if verified > TODAY():
                errors.append(f"{prefix}: verified_at is in the future")
        except (TypeError, ValueError):
            errors.append(f"{prefix}: invalid verified_at date")
        if not str(entry.get("source", "")).startswith("https://"):
            errors.append(f"{prefix}: source must be HTTPS")
        if entry.get("status") not in {
            "stable",
            "preview",
            "deprecated",
            "retired",
        }:
            errors.append(f"{prefix}: invalid status")
    return errors


def docs_errors(root: Path = ROOT) -> list[str]:
    try:
        canonical = load_json_yaml(root / "framework/principles.yaml", root)
    except ValueError as exc:
        return [str(exc)]
    errors: list[str] = []
    for principle in canonical["principles"]:
        for relative in PRINCIPLE_DOCS[principle["id"]]:
            path = root / relative
            text = path.read_text(encoding="utf-8")
            if principle["name"] not in text:
                errors.append(
                    f"{relative}: missing canonical name for {principle['id']}"
                )
            if principle["statement"] not in text:
                errors.append(
                    f"{relative}: missing canonical statement for {principle['id']}"
                )
            if principle["review_question"] not in text:
                errors.append(
                    f"{relative}: missing canonical review question for "
                    f"{principle['id']}"
                )

    link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for path in sorted(root.rglob("*.md")):
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        for target in link_pattern.findall(path.read_text(encoding="utf-8")):
            clean = target.strip().split("#", 1)[0]
            if (
                not clean
                or clean.startswith(("http://", "https://", "mailto:", "#"))
                or clean.startswith("/")
            ):
                continue
            resolved = (path.parent / clean).resolve()
            try:
                resolved.relative_to(root.resolve())
            except ValueError:
                errors.append(
                    f"{path.relative_to(root)}: local link escapes repository "
                    f"{target!r}"
                )
                continue
            if not resolved.exists():
                errors.append(
                    f"{path.relative_to(root)}: broken local link {target!r}"
                )
    return errors


def coverage_markdown(root: Path = ROOT) -> str:
    manifests = [load_json_yaml(path, root) for path in manifest_paths(root)]
    tier_counts: Counter[str] = Counter()
    authority_counts: Counter[str] = Counter()
    exception_count = 0
    status_counts: dict[str, Counter[str]] = {
        principle: Counter()
        for principle in (*PRINCIPLE_CONTROLS, "overlay")
    }
    policy_clean_components = 0
    executable_gates = 0

    for manifest in manifests:
        tier_counts.update([manifest["risk"]["consequence_tier"]])
        authority_counts.update([manifest["authority"]["mode"]])
        exception_count += len(manifest["exceptions"])
        if not manifest["exceptions"]:
            policy_clean_components += 1
        if manifest["evaluation"]["suite"]["command"]:
            executable_gates += 1
        for principle, controls in PRINCIPLE_CONTROLS.items():
            for path in controls:
                status_counts[principle].update(
                    [dotted_get(manifest, f"{path}.status")]
                )
        for path in OVERLAY_CONTROLS:
            status_counts["overlay"].update(
                [dotted_get(manifest, f"{path}.status")]
            )

    lines = [
        "# T.R.U.S.T. verified-control coverage",
        "",
        "Generated by `./trust coverage`, which verifies the referenced artifacts,",
        "hashes, metric results, exception records, and executable suites before",
        "rendering this snapshot. `./trust check` rejects a stale checked-in copy.",
        "",
        f"- Components: {len(manifests)}",
        f"- Components without control exceptions: {policy_clean_components}",
        f"- Executable evaluation gates: {executable_gates}",
        f"- Open component exceptions: {exception_count}",
        "",
        "## Control resolution",
        "",
        "| Area | Enforced | Not applicable | Exception |",
        "|---|---:|---:|---:|",
    ]
    for area in ("T1", "R", "U", "S", "T2", "overlay"):
        counts = status_counts[area]
        lines.append(
            f"| {area} | {counts['enforced']} | "
            f"{counts['not_applicable']} | {counts['exception']} |"
        )

    lines.extend(
        [
            "",
            "## Consequence tiers",
            "",
            "| Tier | Components |",
            "|---|---:|",
        ]
    )
    for tier in ("low", "medium", "high", "critical"):
        lines.append(f"| {tier} | {tier_counts[tier]} |")

    lines.extend(
        [
            "",
            "## Authority modes",
            "",
            "| Mode | Components |",
            "|---|---:|",
        ]
    )
    for mode in (
        "advisory",
        "read_only",
        "reversible_write",
        "irreversible_action",
    ):
        lines.append(f"| {mode} | {authority_counts[mode]} |")

    lines.extend(
        [
            "",
            "Coverage is based on explicit control status. `enforced` controls must",
            "reference verified repository artifacts; `not_applicable` requires a",
            "rationale; `exception` requires an approved, unexpired exception record.",
            "`unsupported` controls are limited to drafts and fail before coverage.",
            "Coverage still does not prove production effectiveness or compliance.",
            "",
        ]
    )
    return "\n".join(lines)

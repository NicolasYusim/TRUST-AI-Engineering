"""Command-line interface for applying T.R.U.S.T. to a repository."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sys
import sysconfig
from collections import defaultdict
from pathlib import Path
from typing import Any

from .framework import (
    ALL_CONTROL_PATHS,
    ROOT,
    coverage_markdown,
    docs_errors,
    manifest_paths,
    registry_errors,
    run_lint,
    run_verify,
)
from .schema import dotted_get, load_json_yaml, sha256_file


CONFIG_VERSION = "1.0"
SPEC_FILES = (
    "schema/trust.schema.json",
    "schema/exception.schema.json",
    "policies/risk-tiers.yaml",
)


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return singular if count == 1 else (plural or f"{singular}s")


def _framework_repository(root: Path) -> bool:
    return all(
        (root / relative).exists()
        for relative in (
            "framework/principles.yaml",
            "schema/trust.schema.json",
            "policies/risk-tiers.yaml",
            "trustlib/framework.py",
        )
    )


def _initialized(root: Path) -> bool:
    return _framework_repository(root) or (root / ".trust/config.json").is_file()


def _installed_specs_root() -> Path:
    candidates = (
        ROOT,
        Path(sysconfig.get_path("data")) / "share/trust-ai",
    )
    for candidate in candidates:
        if all((candidate / relative).is_file() for relative in SPEC_FILES):
            return candidate
    raise FileNotFoundError(
        "T.R.U.S.T. schema and policy files are missing. Reinstall trust-ai."
    )


def _print_errors(errors: list[str]) -> None:
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)


def _init_project(root: Path) -> int:
    if not root.exists() or not root.is_dir():
        print(f"Unable to initialize: project directory does not exist: {root}")
        return 2
    if _framework_repository(root):
        print(f"T.R.U.S.T. is already initialized in {root}")
        return 0

    try:
        specs_root = _installed_specs_root()
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    conflicts: list[str] = []
    for relative in SPEC_FILES:
        source = specs_root / relative
        target = root / ".trust" / relative
        if target.exists() and target.read_bytes() != source.read_bytes():
            conflicts.append(str(target.relative_to(root)))
    if conflicts:
        print("Unable to initialize: these T.R.U.S.T. files contain local changes:")
        for relative in conflicts:
            print(f"- {relative}")
        print("Move or reconcile the files, then run trust init again.")
        return 1

    for relative in SPEC_FILES:
        source = specs_root / relative
        target = root / ".trust" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copyfile(source, target)

    config_path = root / ".trust/config.json"
    already_initialized = config_path.exists()
    if not already_initialized:
        config_path.write_text(
            json.dumps(
                {
                    "schema_version": CONFIG_VERSION,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    for relative in (
        ".trust/components",
        ".trust/exceptions",
        "case-studies/results",
    ):
        (root / relative).mkdir(parents=True, exist_ok=True)

    if already_initialized:
        print(f"T.R.U.S.T. is already initialized in {root}")
    else:
        print(f"✓ Initialized T.R.U.S.T. in {root}")
        print("Next: trust add path/to/ai-component")
    return 0


def _component_id(raw: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")
    if not normalized or not normalized[0].isalpha():
        normalized = f"ai-{normalized or 'component'}"
    if len(normalized) == 1:
        normalized = f"{normalized}-component"
    return normalized


def _repository_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _source_files(source: Path, root: Path) -> list[Path]:
    if source.is_file():
        candidates = [source] if source.suffix == ".py" else []
    else:
        candidates = sorted(source.rglob("*.py"))
    selected: list[Path] = []
    for path in candidates:
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        try:
            path.resolve().relative_to(root)
        except ValueError:
            continue
        selected.append(path)
    return selected


def _matching_tests(root: Path, component: str, sources: list[Path]) -> list[Path]:
    tests_root = root / "tests"
    if not tests_root.is_dir():
        return []
    tokens = {component.replace("-", "_")}
    tokens.update(path.stem.lower() for path in sources)
    matches: list[Path] = []
    for path in sorted(tests_root.rglob("*.py")):
        if not (path.name.startswith("test") or path.name.endswith("_test.py")):
            continue
        try:
            path.resolve().relative_to(root)
        except ValueError:
            continue
        try:
            content = path.read_text(encoding="utf-8").lower()
        except (OSError, UnicodeDecodeError):
            continue
        if any(token and token in content for token in tokens):
            matches.append(path)
    return matches


def _test_ids(path: Path | None, component: str) -> list[str]:
    if path is not None:
        try:
            found = re.findall(
                r"^\s*def\s+(test_[A-Za-z0-9_]+)\s*\(",
                path.read_text(encoding="utf-8"),
                flags=re.MULTILINE,
            )
        except (OSError, UnicodeDecodeError):
            found = []
        if found:
            return list(dict.fromkeys(found))
    return [f"test_{component.replace('-', '_')}_trust_contract"]


def _unsupported() -> dict[str, Any]:
    return {
        "status": "unsupported",
        "rationale": "Evidence has not been reviewed for this generated draft.",
        "evidence": [],
    }


def _not_applicable(rationale: str) -> dict[str, Any]:
    return {
        "status": "not_applicable",
        "rationale": rationale,
        "evidence": [],
    }


def _draft_manifest(
    component: str,
    owner: str,
    code_paths: list[str],
    test_paths: list[str],
    test_path: str,
    suite_hash: str,
    test_ids: list[str],
) -> dict[str, Any]:
    today = str(dt.date.today())
    evidence_path = f"case-studies/results/{component}.json"
    inactive_confirmation = _not_applicable(
        "The generated draft starts in advisory mode with no external effects."
    )
    inactive_confirmation.update(
        {"identity_source": "not_applicable", "bound_to_plan": False}
    )
    inactive_idempotency = _not_applicable(
        "The generated draft starts in advisory mode with no external writes."
    )
    inactive_idempotency.update(
        {"key_scope": "not_applicable", "payload_binding": False}
    )
    inactive_transaction = _not_applicable(
        "The generated draft starts in advisory mode with no effects to reverse."
    )
    inactive_transaction.update(
        {
            "strategy": "not_applicable",
            "rollback_or_compensation": (
                "No write effects are declared in advisory mode."
            ),
        }
    )
    inactive_approval = _not_applicable(
        "The generated draft starts in advisory mode with no irreversible action."
    )
    inactive_approval.update(
        {"identity_source": "not_applicable", "independent_from_owner": False}
    )

    return {
        "schema_version": "2.0",
        "lifecycle": "draft",
        "component": component,
        "description": f"Generated assurance draft for the {component} AI component.",
        "owner": owner,
        "risk": {
            "consequence_tier": "low",
            "likelihood": "possible",
            "exposure": "internal",
            "detectability": "medium",
            "rationale": (
                "Generated default; review the real consequence and exposure "
                "before activation."
            ),
            "reviewed_by": "unassigned-reviewer",
            "reviewed_at": today,
        },
        "implementation": {"code": code_paths, "tests": test_paths},
        "data": {
            "classification": "internal",
            "pii_allowed": False,
            "retention_days": {
                "value": 0,
                "unit": "days",
                "basis": "illustrative",
                "rationale": (
                    "Generated placeholder; apply the component data-retention "
                    "policy."
                ),
            },
        },
        "authority": {
            "mode": "advisory",
            "allowed_tools": [],
            "allowed_resources": [],
            "allowed_network_destinations": [],
            "max_effects": {
                "value": 0,
                "unit": "effects",
                "basis": "illustrative",
                "rationale": (
                    "Generated advisory default; review transitive tool authority."
                ),
            },
            "confirmation": inactive_confirmation,
            "idempotency": inactive_idempotency,
            "transaction_or_compensation": inactive_transaction,
            "independent_approval": inactive_approval,
        },
        "traceability": {
            "prompt_versioning": _unsupported(),
            "input_provenance": _unsupported(),
            "input_provenance_method": "artifact_reference",
            "source_provenance": _unsupported(),
            "source_provenance_method": "artifact_reference",
            "tool_event_logging": _unsupported(),
        },
        "resilience": {
            "timeout_ms": {
                "value": 30000,
                "unit": "ms",
                "basis": "illustrative",
                "rationale": (
                    "Generated placeholder; measure the component total deadline."
                ),
            },
            "max_attempts": {
                "value": 1,
                "unit": "attempts",
                "basis": "illustrative",
                "rationale": (
                    "Generated placeholder; review retry and fallback behavior."
                ),
            },
            "failure_mode": "fail_closed",
            "fallback": (
                "Generated default; define the observable behavior when the AI "
                "path fails."
            ),
            "owner": owner,
            "bounded_recovery": _unsupported(),
            "service_objective": _unsupported(),
        },
        "utility": {
            "expected_benefit": _unsupported(),
            "latency_slo_ms": {
                "value": 30000,
                "unit": "ms",
                "basis": "illustrative",
                "rationale": (
                    "Generated placeholder; replace it with a measured objective."
                ),
            },
            "monthly_budget_usd": {
                "value": 0,
                "unit": "USD/month",
                "basis": "illustrative",
                "rationale": (
                    "Generated placeholder; define the component budget and "
                    "evidence basis."
                ),
            },
            "output_token_limit": {
                "value": 1,
                "unit": "reference_tokens",
                "basis": "illustrative",
                "rationale": (
                    "Generated placeholder; define and test the actual output bound."
                ),
            },
            "resource_bounds": _unsupported(),
        },
        "evaluation": {
            "suite": {
                "path": test_path,
                "sha256": suite_hash,
                "command": [
                    "python3",
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "tests",
                    "-p",
                    Path(test_path).name,
                    "-v",
                ],
                "test_ids": test_ids,
                "population": (
                    "Generated draft; define the evaluated population and exclusions."
                ),
                "evaluated_at": today,
                "evidence": evidence_path,
            },
            "blocking_metrics": {},
            "slices": [],
            "uncertainty_control": _unsupported(),
            "slice_analysis": _unsupported(),
            "oversight": _unsupported(),
        },
        "security": {
            "threat_model": _unsupported(),
            "tenant_isolation": "not_applicable",
            "secrets": _unsupported(),
            "sandbox": _unsupported(),
            "audit": _unsupported(),
        },
        "operations": {
            "alerts": _unsupported(),
            "runbook": _unsupported(),
        },
        "exceptions": [],
    }


def _add_component(
    root: Path,
    raw_path: str,
    requested_name: str | None,
    owner: str,
) -> int:
    if not _initialized(root):
        print(f"No T.R.U.S.T. project found in {root}.")
        print("Run: trust init")
        return 2
    source = (root / raw_path).resolve()
    try:
        source.relative_to(root)
    except ValueError:
        print("Unable to add component: source path must stay inside the project.")
        return 2
    if not source.exists():
        print(f"Unable to add component: source path does not exist: {raw_path}")
        return 2
    if len(owner.strip()) < 8 or owner.strip().lower() in {
        "none",
        "n/a",
        "todo",
        "tbd",
    }:
        print("Unable to add component: --owner must name an accountable team.")
        print("Use at least 8 characters, for example: --owner agent-platform")
        return 2

    sources = _source_files(source, root)
    if not sources:
        print(f"No Python source files found under {raw_path}.")
        print("Pass a Python file or a directory containing Python source files.")
        return 1

    default_name = source.stem if source.is_file() else source.name
    component = _component_id(requested_name or default_name)
    manifest_path = root / ".trust/components" / component / "trust.yaml"
    if manifest_path.exists():
        print(f"Component already exists: .trust/components/{component}/trust.yaml")
        print("Choose another name with --name or edit the existing manifest.")
        return 1

    tests = _matching_tests(root, component, sources)
    expected_test = root / "tests" / f"test_{component.replace('-', '_')}.py"
    suite_path = tests[0] if tests else expected_test
    suite_hash = sha256_file(suite_path) if suite_path.is_file() else "0" * 64
    manifest = _draft_manifest(
        component,
        owner,
        [_repository_path(path, root) for path in sources],
        (
            [_repository_path(path, root) for path in tests]
            if tests
            else [_repository_path(expected_test, root)]
        ),
        _repository_path(suite_path, root),
        suite_hash,
        _test_ids(suite_path if suite_path.is_file() else None, component),
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"✓ Added component draft: {component}")
    print(f"  Manifest: .trust/components/{component}/trust.yaml")
    print(f"  Source: {len(sources)} {_plural(len(sources), 'Python file')}")
    if tests:
        print(f"  Tests: {len(tests)} matching {_plural(len(tests), 'file')} found")
    else:
        print(f"  Tests: none found; expected {_repository_path(expected_test, root)}")
    print("Next:")
    print("  1. Review risk, authority, and data scope in the manifest.")
    print(
        "  2. Replace unsupported controls with evidence, a permitted N/A, "
        "or an exception."
    )
    print("  3. Add evaluation results, set lifecycle to active, and run trust check.")
    return 0


def _manifest_value(path: Path, root: Path) -> dict[str, Any] | None:
    try:
        value = load_json_yaml(path, root)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def _unsupported_controls(manifest: dict[str, Any]) -> list[str]:
    controls: list[str] = []
    for path in ALL_CONTROL_PATHS:
        try:
            if dotted_get(manifest, f"{path}.status") == "unsupported":
                controls.append(path)
        except KeyError:
            continue
    return controls


def _verified_control_count(manifest: dict[str, Any]) -> int:
    count = 0
    for path in ALL_CONTROL_PATHS:
        try:
            count += dotted_get(manifest, f"{path}.status") == "enforced"
        except KeyError:
            continue
    return count


def _actionable_error(error: str, label: str) -> str:
    detail = error.removeprefix(f"{label}: ").replace("$.", "")
    if "evaluation.suite.sha256" in detail:
        return "evaluation suite hash is stale; update the hash and result artifact"
    if "exception is expired" in detail:
        return (
            "control exception has expired; enforce the control or renew "
            "independent approval"
        )
    if "path does not exist" in detail:
        missing = detail.rsplit(": ", 1)[-1]
        return f"referenced evidence is missing: {missing}"
    if "evaluation command failed" in detail:
        return (
            "evaluation suite failed; run its declared command locally and fix "
            "the test"
        )
    if "did not report required test" in detail:
        return (
            "evaluation command did not report a required test ID; update the "
            "suite mapping"
        )
    if "evidence contains" in detail and ".observed" in detail:
        return (
            "declared metric differs from the result artifact; regenerate or "
            "correct the evidence"
        )
    if "tier/policy requires enforced or exception" in detail:
        control = detail.split(".status", 1)[0]
        return f"{control}: add evidence or reference an approved exception"
    return detail


def _print_component_failure(
    component: str,
    relative: str,
    manifest: dict[str, Any] | None,
    errors: list[str],
    root: Path,
) -> None:
    unsupported = _unsupported_controls(manifest) if manifest else []
    if manifest and manifest.get("lifecycle") == "draft":
        print(f"✗ {component}: manifest is still a draft")
        print(
            "  Review risk and authority, complete the evidence, then set "
            "lifecycle to active."
        )
    if unsupported:
        print(
            f"✗ {component}: {len(unsupported)} "
            f"{_plural(len(unsupported), 'control')} need evidence decisions"
        )
        by_area: dict[str, list[str]] = defaultdict(list)
        for control in unsupported:
            area, name = control.split(".", 1)
            by_area[area].append(name)
        for area, names in by_area.items():
            print(f"  - {area}: {', '.join(names)}")
        print(
            "  Add evidence, use a permitted N/A rationale, or link an approved "
            "exception."
        )

    if manifest:
        implementation = manifest.get("implementation")
        if not isinstance(implementation, dict):
            implementation = {}
        tests = implementation.get("tests", [])
        if not isinstance(tests, list):
            tests = []
        for test_path in tests:
            if not isinstance(test_path, str):
                continue
            if not (root / test_path).is_file():
                print(f"✗ {component}: test evidence is missing: {test_path}")
        evaluation = manifest.get("evaluation")
        if not isinstance(evaluation, dict):
            evaluation = {}
        suite = evaluation.get("suite")
        if not isinstance(suite, dict):
            suite = {}
        evidence_path = suite.get("evidence")
        if isinstance(evidence_path, str) and not (root / evidence_path).is_file():
            print(f"✗ {component}: evaluation result is missing: {evidence_path}")

    filtered: list[str] = []
    for error in errors:
        if "unsupported control requires" in error:
            continue
        if "$.lifecycle: draft manifest cannot pass" in error:
            continue
        if unsupported and "tier/policy requires enforced or exception" in error:
            continue
        action = _actionable_error(error, relative)
        if action not in filtered:
            filtered.append(action)
    for action in filtered:
        print(f"✗ {component}: {action}")


def _check_project(root: Path) -> int:
    paths = manifest_paths(root)
    if not paths:
        print("✗ No AI components found")
        print("Run: trust add path/to/ai-component")
        print("\nTRUST check failed")
        return 1

    print(f"✓ {len(paths)} AI {_plural(len(paths), 'component')} found")
    verified_controls = 0
    suites = 0
    failed = False
    for path in paths:
        relative = _repository_path(path, root)
        component = path.parent.name
        manifest = _manifest_value(path, root)
        _, lint_errors = run_lint([relative], root=root)
        errors = list(lint_errors)
        commands = 0
        if not errors:
            _, commands, verify_errors = run_verify(
                [relative],
                root=root,
                skip_lint=True,
            )
            errors.extend(verify_errors)
        if errors:
            failed = True
            _print_component_failure(
                component,
                relative,
                manifest,
                errors,
                root,
            )
        elif manifest is not None:
            verified_controls += _verified_control_count(manifest)
            suites += commands

    if verified_controls:
        print(
            f"✓ {verified_controls} verified "
            f"{_plural(verified_controls, 'control')}"
        )
    if suites:
        print(f"✓ {suites} evaluation {_plural(suites, 'suite')} passed")
    print(f"\nTRUST check {'failed' if failed else 'passed'}")
    return 1 if failed else 0


def _check_framework(root: Path) -> int:
    count, lint_errors = run_lint(root=root)
    errors = list(lint_errors)
    commands = 0
    if not errors:
        _, commands, verify_errors = run_verify(root=root, skip_lint=True)
        errors.extend(verify_errors)
    errors.extend(registry_errors(root))
    errors.extend(docs_errors(root))
    if not lint_errors:
        snapshot = root / "reports/coverage.md"
        if (
            not snapshot.exists()
            or snapshot.read_text(encoding="utf-8") != coverage_markdown(root)
        ):
            errors.append("reports/coverage.md: snapshot differs from trust coverage")
    if errors:
        _print_errors(errors)
        return 1
    print(
        f"OK: {count} manifests, evidence, {commands} evaluation command(s), "
        "registry, docs, links, and coverage"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="trust")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help=argparse.SUPPRESS,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="initialize T.R.U.S.T. in this repository")
    add_parser = subparsers.add_parser(
        "add",
        help="create an evidence-safe draft manifest for an AI component",
    )
    add_parser.add_argument("path")
    add_parser.add_argument("--name")
    add_parser.add_argument("--owner", default="unassigned-owner")

    lint_parser = subparsers.add_parser(
        "lint", help="validate manifest declarations and policy semantics"
    )
    lint_parser.add_argument("paths", nargs="*")
    verify_parser = subparsers.add_parser(
        "verify",
        help="verify evidence, hashes, results, exceptions, and run eval suites",
    )
    verify_parser.add_argument("paths", nargs="*")
    coverage_parser = subparsers.add_parser(
        "coverage", help="report resolved control status"
    )
    coverage_parser.add_argument("--check", metavar="PATH")
    subparsers.add_parser("docs", help="check canonical docs and local links")
    registry_parser = subparsers.add_parser(
        "registry", help="validate model registry"
    )
    registry_parser.add_argument("action", choices=["lint"])
    subparsers.add_parser(
        "check", help="verify component claims and return a repository decision"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()

    if args.command == "init":
        return _init_project(root)
    if args.command == "add":
        return _add_component(root, args.path, args.name, args.owner)
    if not _initialized(root):
        print(f"No T.R.U.S.T. project found in {root}.")
        print("Run: trust init")
        return 2

    if args.command == "lint":
        count, errors = run_lint(args.paths, root=root)
        if errors:
            _print_errors(errors)
            return 1
        print(f"OK: {count} component declaration(s)")
        return 0
    if args.command == "verify":
        count, commands, errors = run_verify(args.paths, root=root)
        if errors:
            _print_errors(errors)
            return 1
        print(
            f"OK: {count} component evidence contract(s), "
            f"{commands} unique evaluation command(s)"
        )
        return 0
    if args.command == "coverage":
        _, _, errors = run_verify(root=root)
        if errors:
            _print_errors(errors)
            return 1
        rendered = coverage_markdown(root)
        if args.check:
            target = root / args.check
            if not target.exists() or target.read_text(encoding="utf-8") != rendered:
                print(
                    f"ERROR: coverage snapshot differs: {args.check}",
                    file=sys.stderr,
                )
                return 1
            print(f"OK: coverage snapshot matches {args.check}")
            return 0
        print(rendered, end="")
        return 0
    if args.command == "docs":
        if not _framework_repository(root):
            print(
                "The docs command is only available in the T.R.U.S.T. source "
                "repository."
            )
            return 2
        errors = docs_errors(root)
        if errors:
            _print_errors(errors)
            return 1
        print("OK: canonical documentation and local links")
        return 0
    if args.command == "registry":
        if not _framework_repository(root):
            print(
                "The registry command is only available in the T.R.U.S.T. "
                "source repository."
            )
            return 2
        errors = registry_errors(root)
        if errors:
            _print_errors(errors)
            return 1
        print("OK: model registry")
        return 0
    if args.command == "check":
        if _framework_repository(root):
            return _check_framework(root)
        return _check_project(root)
    return 2

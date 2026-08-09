from __future__ import annotations

import datetime as dt
import importlib.machinery
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from helpers import ROOT
from trustlib import framework


def load_trust_cli():
    loader = importlib.machinery.SourceFileLoader("trust_cli", str(ROOT / "trust"))
    spec = importlib.util.spec_from_loader("trust_cli", loader)
    if spec is None:
        raise RuntimeError("cannot load trust CLI")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


trust_cli = load_trust_cli()


class FrameworkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(
            (ROOT / "schema/trust.schema.json").read_text()
        )
        cls.policy = trust_cli.load_json_yaml(
            ROOT / "policies/risk-tiers.yaml"
        )

    def load_manifest(self, component: str) -> dict:
        return json.loads(
            (ROOT / f"components/{component}/trust.yaml").read_text()
        )

    def lint_mutation(self, component: str, manifest: dict) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / component / "trust.yaml"
            path.parent.mkdir()
            path.write_text(json.dumps(manifest))
            return trust_cli.lint_manifest(
                path,
                self.schema,
                self.policy,
            )

    def verify_mutation(self, component: str, manifest: dict) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / component / "trust.yaml"
            path.parent.mkdir()
            path.write_text(json.dumps(manifest))
            errors, _ = trust_cli.verify_manifest(path, self.policy)
            return errors

    def test_all_manifests_pass_schema_and_policy(self):
        count, errors = trust_cli.run_lint()
        self.assertEqual(8, count)
        self.assertEqual([], errors)

    def test_all_manifest_evidence_contracts_verify_without_execution(self):
        count, commands, errors = trust_cli.run_verify(
            execute_commands=False
        )
        self.assertEqual(8, count)
        self.assertEqual(0, commands)
        self.assertEqual([], errors)

    def test_docs_and_registry_are_current(self):
        self.assertEqual([], trust_cli.docs_errors())
        self.assertEqual([], trust_cli.registry_errors())

    def test_coverage_snapshot_is_generated_output(self):
        expected = (ROOT / "reports/coverage.md").read_text()
        self.assertEqual(expected, trust_cli.coverage_markdown())

    def test_high_risk_tool_logging_cannot_be_not_applicable(self):
        source = self.load_manifest("support-ticket-router")
        source["traceability"]["tool_event_logging"] = {
            "status": "not_applicable",
            "rationale": "Mutation disables required action logging.",
            "evidence": [],
        }
        errors = self.lint_mutation("support-ticket-router", source)
        self.assertTrue(
            any(
                "tool_event_logging.status" in error
                and "requires enforced or exception" in error
                for error in errors
            ),
            errors,
        )

    def test_required_prompt_versioning_cannot_be_not_applicable(self):
        source = self.load_manifest("support-answer-generator")
        source["traceability"]["prompt_versioning"] = {
            "status": "not_applicable",
            "rationale": "Mutation disables required prompt version evidence.",
            "evidence": [],
        }
        errors = self.lint_mutation("support-answer-generator", source)
        self.assertTrue(
            any(
                "prompt_versioning.status" in error
                and "requires enforced or exception" in error
                for error in errors
            ),
            errors,
        )

    def test_high_risk_write_requires_payload_bound_idempotency(self):
        source = self.load_manifest("support-ticket-router")
        source["authority"]["idempotency"] = {
            "status": "not_applicable",
            "rationale": "Mutation removes write idempotency.",
            "evidence": [],
            "key_scope": "not_applicable",
            "payload_binding": False,
        }
        errors = self.lint_mutation("support-ticket-router", source)
        self.assertTrue(
            any(
                "authority.idempotency.status" in error
                and "requires enforced or exception" in error
                for error in errors
            ),
            errors,
        )

    def test_write_confirmation_must_be_bound_to_plan_and_identity(self):
        source = self.load_manifest("support-ticket-router")
        source["authority"]["confirmation"]["bound_to_plan"] = False
        source["authority"]["confirmation"][
            "identity_source"
        ] = "not_applicable"
        errors = self.lint_mutation("support-ticket-router", source)
        self.assertTrue(
            any("requires action-bound confirmation" in error for error in errors),
            errors,
        )
        self.assertTrue(
            any("requires an authenticated approval identity" in error for error in errors),
            errors,
        )

    def test_readme_cannot_masquerade_as_evaluation_suite(self):
        source = self.load_manifest("support-ticket-router")
        source["evaluation"]["suite"]["path"] = "README.md"
        errors = self.lint_mutation("support-ticket-router", source)
        self.assertTrue(
            any("suite.path" in error and "tests/ or evals/" in error for error in errors),
            errors,
        )

    def test_blocking_metric_cannot_be_illustrative(self):
        source = self.load_manifest("support-answer-generator")
        metric = source["evaluation"]["blocking_metrics"][
            "approved_source_citation_rate"
        ]
        metric["basis"] = "illustrative"
        errors = self.lint_mutation("support-answer-generator", source)
        self.assertTrue(
            any(
                "blocking_metrics.approved_source_citation_rate.basis" in error
                for error in errors
            ),
            errors,
        )

    def test_active_manifest_requires_a_blocking_metric(self):
        source = self.load_manifest("support-answer-generator")
        source["evaluation"]["blocking_metrics"] = {}
        errors = self.lint_mutation("support-answer-generator", source)
        self.assertTrue(
            any("active manifests require at least one" in error for error in errors),
            errors,
        )

    def test_metric_test_id_must_belong_to_executable_suite(self):
        source = self.load_manifest("support-answer-generator")
        source["evaluation"]["blocking_metrics"][
            "approved_source_citation_rate"
        ]["test_ids"] = ["test_phantom_metric"]
        errors = self.lint_mutation("support-answer-generator", source)
        self.assertTrue(
            any("not declared by the suite" in error for error in errors),
            errors,
        )

    def test_metric_test_id_must_match_evidence_mapping(self):
        source = self.load_manifest("support-answer-generator")
        source["evaluation"]["blocking_metrics"][
            "approved_source_citation_rate"
        ]["test_ids"] = ["test_unsupported_question_abstains"]
        errors = self.verify_mutation("support-answer-generator", source)
        self.assertTrue(
            any("must equal" in error and "result_tests" in error for error in errors),
            errors,
        )

    def test_verify_rejects_a_test_id_missing_from_command_output(self):
        completed = subprocess.CompletedProcess(
            args=["python3"],
            returncode=0,
            stdout="Ran 1 test\nOK\n",
            stderr="",
        )
        with mock.patch.object(framework.subprocess, "run", return_value=completed):
            _, commands, errors = framework.run_verify(
                ["components/support-answer-generator/trust.yaml"]
            )
        self.assertEqual(1, commands)
        self.assertTrue(
            any("did not report required test" in error for error in errors),
            errors,
        )

    def test_generic_overlay_is_not_component_threat_model_evidence(self):
        source = self.load_manifest("support-ticket-router")
        source["security"]["threat_model"]["evidence"] = [
            "docs/security-privacy-overlay.md"
        ]
        errors = self.verify_mutation("support-ticket-router", source)
        self.assertTrue(
            any("security.threat_model.evidence" in error for error in errors),
            errors,
        )

    def test_placeholder_control_text_is_rejected(self):
        source = self.load_manifest("support-answer-generator")
        source["security"]["threat_model"]["rationale"] = "none"
        errors = self.lint_mutation("support-answer-generator", source)
        self.assertTrue(
            any("threat_model.rationale" in error for error in errors),
            errors,
        )

    def test_plain_none_cannot_replace_structured_controls(self):
        for section, field in (
            ("security", "sandbox"),
            ("operations", "alerts"),
            ("operations", "runbook"),
        ):
            with self.subTest(control=f"{section}.{field}"):
                source = self.load_manifest("support-ticket-router")
                source[section][field] = "none"
                errors = self.lint_mutation("support-ticket-router", source)
                self.assertTrue(
                    any(f"{section}.{field}" in error for error in errors),
                    errors,
                )

    def test_nonexistent_exception_id_is_rejected(self):
        source = self.load_manifest("support-answer-generator")
        source["security"]["threat_model"] = {
            "status": "exception",
            "rationale": "Temporary mutation exception for a required control.",
            "evidence": [],
            "exception_id": "EXC-2026-999",
        }
        source["exceptions"] = ["EXC-2026-999"]
        errors = self.lint_mutation("support-answer-generator", source)
        self.assertTrue(
            any("exception file does not exist" in error for error in errors),
            errors,
        )

    def test_exception_expiry_and_independent_approval_are_verified(self):
        source = self.load_manifest("support-ticket-router")
        source["security"]["threat_model"] = {
            "status": "exception",
            "rationale": "Temporary exception used to exercise expiry validation.",
            "evidence": [],
            "exception_id": "EXC-2026-001",
        }
        source["exceptions"] = ["EXC-2026-001"]
        today = framework.TODAY()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = root / "tests/evidence.py"
            evidence.parent.mkdir(parents=True)
            evidence.write_text("# exception evidence\n")
            exception_path = root / "exceptions/EXC-2026-001.yaml"
            exception_path.parent.mkdir(parents=True)
            exception_path.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "id": "EXC-2026-001",
                        "component": "support-ticket-router",
                        "control": "security.threat_model",
                        "owner": "same-risk-owner",
                        "approver": "same-risk-owner",
                        "created": str(today - dt.timedelta(days=10)),
                        "expires": str(today - dt.timedelta(days=1)),
                        "risk": "Threat-model evidence is temporarily incomplete.",
                        "reason": "Mutation fixture exercises the verifier.",
                        "compensating_control": "Writes remain disabled during the exception.",
                        "review_plan": "Remove the exception after evidence review.",
                        "evidence": ["tests/evidence.py"],
                    }
                )
            )
            errors = framework._verify_exceptions(
                source,
                self.policy,
                root,
                "support-ticket-router",
            )
            valid_exception = json.loads(exception_path.read_text())
            valid_exception["owner"] = "accountable-control-owner"
            valid_exception["approver"] = "independent-risk-approver"
            valid_exception["created"] = str(today - dt.timedelta(days=1))
            valid_exception["expires"] = str(today + dt.timedelta(days=30))
            exception_path.write_text(json.dumps(valid_exception))
            valid_errors = framework._verify_exceptions(
                source,
                self.policy,
                root,
                "support-ticket-router",
            )
        self.assertTrue(any("expired" in error for error in errors), errors)
        self.assertTrue(
            any("owner and approver must be independent" in error for error in errors),
            errors,
        )
        self.assertEqual([], valid_errors)

    def test_critical_action_requires_independent_approval_and_slices(self):
        source = self.load_manifest("support-ticket-router")
        source["risk"]["consequence_tier"] = "critical"
        source["authority"]["mode"] = "irreversible_action"
        errors = self.lint_mutation("support-ticket-router", source)
        self.assertTrue(
            any("independent_approval.status" in error for error in errors),
            errors,
        )
        self.assertTrue(
            any("requires at least 2 slice" in error for error in errors),
            errors,
        )

    def test_suite_hash_drift_is_detected(self):
        source = self.load_manifest("support-answer-generator")
        source["evaluation"]["suite"]["sha256"] = "0" * 64
        errors = self.verify_mutation("support-answer-generator", source)
        self.assertTrue(any("suite.sha256" in error for error in errors), errors)

    def test_observed_metric_must_match_evidence_artifact(self):
        source = self.load_manifest("support-answer-generator")
        source["evaluation"]["blocking_metrics"][
            "approved_source_citation_rate"
        ]["observed"] = 1.1
        errors = self.verify_mutation("support-answer-generator", source)
        self.assertTrue(
            any("observed" in error and "evidence contains" in error for error in errors),
            errors,
        )

    def test_unit_must_match_field_semantics(self):
        source = self.load_manifest("faq-answerer")
        source["utility"]["output_token_limit"]["unit"] = "characters"
        errors = self.lint_mutation("faq-answerer", source)
        self.assertTrue(
            any("output_token_limit.unit" in error for error in errors),
            errors,
        )

    def test_cli_check(self):
        result = subprocess.run(
            [sys.executable, "trust", "check"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
    unittest.main()

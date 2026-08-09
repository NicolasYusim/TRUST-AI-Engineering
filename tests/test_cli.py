from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from trustlib import cli
from trustlib.schema import sha256_file, validate_schema


class CliAdoptionTests(unittest.TestCase):
    def run_cli(self, root: Path, *arguments: str) -> tuple[int, str]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            result = cli.main(["--root", str(root), *arguments])
        return result, output.getvalue()

    def initialize(self, root: Path) -> None:
        result, output = self.run_cli(root, "init")
        self.assertEqual(0, result, output)

    def test_init_creates_self_contained_project_specs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result, output = self.run_cli(root, "init")

            self.assertEqual(0, result, output)
            self.assertIn("Initialized T.R.U.S.T.", output)
            self.assertTrue((root / ".trust/config.json").is_file())
            self.assertTrue((root / ".trust/schema/trust.schema.json").is_file())
            self.assertTrue((root / ".trust/schema/exception.schema.json").is_file())
            self.assertTrue((root / ".trust/policies/risk-tiers.yaml").is_file())

            second_result, second_output = self.run_cli(root, "init")
            self.assertEqual(0, second_result, second_output)
            self.assertIn("already initialized", second_output)

    def test_add_creates_schema_valid_draft_without_false_enforcement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "src/agent"
            source.mkdir(parents=True)
            (source / "graph.py").write_text("def run():\n    return 'ok'\n")
            self.initialize(root)

            result, output = self.run_cli(root, "add", "src/agent")

            self.assertEqual(0, result, output)
            self.assertIn("Added component draft: agent", output)
            manifest_path = root / ".trust/components/agent/trust.yaml"
            manifest = json.loads(manifest_path.read_text())
            schema = json.loads(
                (root / ".trust/schema/trust.schema.json").read_text()
            )
            self.assertEqual([], validate_schema(manifest, schema, schema))
            self.assertEqual("draft", manifest["lifecycle"])
            self.assertEqual(
                ["src/agent/graph.py"],
                manifest["implementation"]["code"],
            )
            statuses = json.dumps(manifest)
            self.assertIn('"status": "unsupported"', statuses)
            self.assertNotIn('"status": "enforced"', statuses)

            check_result, check_output = self.run_cli(root, "check")
            self.assertEqual(1, check_result, check_output)
            self.assertIn("✓ 1 AI component found", check_output)
            self.assertIn("✗ agent: manifest is still a draft", check_output)
            self.assertIn("controls need evidence decisions", check_output)
            self.assertIn("test evidence is missing", check_output)
            self.assertIn("evaluation result is missing", check_output)
            self.assertTrue(check_output.rstrip().endswith("TRUST check failed"))

            lint_result, lint_output = self.run_cli(root, "lint")
            self.assertEqual(1, lint_result, lint_output)
            self.assertIn("draft manifest cannot pass", lint_output)

    def test_add_does_not_overwrite_an_existing_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "src/agent"
            source.mkdir(parents=True)
            (source / "agent.py").write_text("def run():\n    return True\n")
            self.initialize(root)
            first_result, first_output = self.run_cli(root, "add", "src/agent")
            self.assertEqual(0, first_result, first_output)
            manifest_path = root / ".trust/components/agent/trust.yaml"
            original = manifest_path.read_text()

            second_result, second_output = self.run_cli(root, "add", "src/agent")

            self.assertEqual(1, second_result, second_output)
            self.assertIn("Component already exists", second_output)
            self.assertEqual(original, manifest_path.read_text())

    def test_add_links_matching_tests_and_hashes_the_suite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "src/agent"
            source.mkdir(parents=True)
            (source / "graph.py").write_text("def run():\n    return True\n")
            test = root / "tests/test_graph.py"
            test.parent.mkdir(parents=True)
            test.write_text(
                "from src.agent.graph import run\n\n"
                "def test_graph_contract():\n"
                "    assert run() is True\n"
            )
            self.initialize(root)

            result, output = self.run_cli(root, "add", "src/agent")

            self.assertEqual(0, result, output)
            self.assertIn("Tests: 1 matching file found", output)
            manifest = json.loads(
                (root / ".trust/components/agent/trust.yaml").read_text()
            )
            self.assertEqual(
                ["tests/test_graph.py"],
                manifest["implementation"]["tests"],
            )
            self.assertEqual(
                sha256_file(test),
                manifest["evaluation"]["suite"]["sha256"],
            )
            self.assertEqual(
                ["test_graph_contract"],
                manifest["evaluation"]["suite"]["test_ids"],
            )

    def test_check_reports_a_malformed_manifest_without_crashing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.initialize(root)
            manifest_path = root / ".trust/components/agent/trust.yaml"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": "2.0",
                        "component": "agent",
                        "implementation": [],
                    }
                )
            )

            result, output = self.run_cli(root, "check")

            self.assertEqual(1, result, output)
            self.assertIn("✓ 1 AI component found", output)
            self.assertIn("✗ agent:", output)
            self.assertTrue(output.rstrip().endswith("TRUST check failed"))

    def write_active_component(self, root: Path) -> Path:
        self.initialize(root)
        source = root / "src/agent.py"
        source.parent.mkdir(parents=True)
        source.write_text("def run():\n    return 'bounded'\n")
        test = root / "tests/test_agent.py"
        test.parent.mkdir(parents=True)
        test.write_text(
            "import unittest\n"
            "from src.agent import run\n\n"
            "class AgentTests(unittest.TestCase):\n"
            "    def test_agent_contract(self):\n"
            "        self.assertEqual('bounded', run())\n"
        )
        (root / "docs/threat-models").mkdir(parents=True)
        (root / "docs/threat-models/agent.md").write_text(
            "# Agent threat model\n\nThe advisory component has no tools.\n"
        )
        (root / "docs/runbooks").mkdir(parents=True)
        (root / "docs/runbooks/agent.md").write_text(
            "# Agent runbook\n\nDisable the advisory component on failure.\n"
        )

        suite_hash = sha256_file(test)
        test_ids = ["test_agent_contract"]
        manifest = cli._draft_manifest(
            "agent",
            "agent-platform",
            ["src/agent.py"],
            ["tests/test_agent.py"],
            "tests/test_agent.py",
            suite_hash,
            test_ids,
        )
        manifest["lifecycle"] = "active"
        code_evidence = ["src/agent.py", "tests/test_agent.py"]
        result_evidence = ["case-studies/results/agent.json"]
        manifest["traceability"]["prompt_versioning"] = {
            "status": "enforced",
            "rationale": (
                "The callable contract is versioned with the component source."
            ),
            "evidence": code_evidence,
        }
        manifest["traceability"]["input_provenance"] = {
            "status": "enforced",
            "rationale": (
                "The advisory input is an explicit versioned function argument."
            ),
            "evidence": code_evidence,
        }
        manifest["resilience"]["bounded_recovery"] = {
            "status": "enforced",
            "rationale": (
                "The deterministic advisory path has no retry or fallback loop."
            ),
            "evidence": code_evidence,
        }
        manifest["resilience"]["service_objective"] = {
            "status": "enforced",
            "rationale": (
                "The committed result measures the declared advisory contract."
            ),
            "evidence": result_evidence,
        }
        manifest["utility"]["expected_benefit"] = {
            "status": "enforced",
            "rationale": "The committed result verifies the bounded advisory response.",
            "evidence": result_evidence,
        }
        manifest["utility"]["resource_bounds"] = {
            "status": "enforced",
            "rationale": "The implementation performs one deterministic bounded call.",
            "evidence": code_evidence,
        }
        manifest["evaluation"]["uncertainty_control"] = {
            "status": "enforced",
            "rationale": (
                "The test verifies the complete deterministic response contract."
            ),
            "evidence": ["tests/test_agent.py"],
        }
        manifest["security"]["threat_model"] = {
            "status": "enforced",
            "rationale": (
                "The component-specific threat model covers its advisory boundary."
            ),
            "evidence": ["docs/threat-models/agent.md"],
        }
        manifest["operations"]["runbook"] = {
            "status": "enforced",
            "rationale": "The component runbook defines the explicit failure response.",
            "evidence": ["docs/runbooks/agent.md"],
        }
        for section, field, rationale in (
            (
                "traceability",
                "source_provenance",
                "The deterministic response uses no external sources.",
            ),
            (
                "traceability",
                "tool_event_logging",
                "The advisory component has no callable tools.",
            ),
            (
                "evaluation",
                "slice_analysis",
                "The deterministic unit fixture has no population slices.",
            ),
            (
                "evaluation",
                "oversight",
                "Low-consequence deterministic output needs no review gate.",
            ),
            (
                "security",
                "secrets",
                "The component has no provider or service credentials.",
            ),
            (
                "security",
                "sandbox",
                "The component has no tools, network access, or side effects.",
            ),
            (
                "security",
                "audit",
                "The deterministic advisory result causes no external effect.",
            ),
            (
                "operations",
                "alerts",
                "The offline component has no deployed alert destination.",
            ),
        ):
            manifest[section][field] = cli._not_applicable(rationale)
        manifest["traceability"]["source_provenance_method"] = "not_applicable"
        manifest["evaluation"]["blocking_metrics"] = {
            "control_readiness": {
                "comparator": ">=",
                "threshold": 1.0,
                "observed": 1.0,
                "unit": "ratio",
                "basis": "measured",
                "rationale": "The complete committed advisory contract must pass.",
                "evidence": "case-studies/results/agent.json",
                "result_key": "metrics.control_readiness",
                "test_ids": test_ids,
            }
        }
        manifest_path = root / ".trust/components/agent/trust.yaml"
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

        result_path = root / "case-studies/results/agent.json"
        result_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "evaluated_at": manifest["evaluation"]["suite"]["evaluated_at"],
                    "population": manifest["evaluation"]["suite"]["population"],
                    "command": manifest["evaluation"]["suite"]["command"],
                    "test_ids": test_ids,
                    "result_tests": {
                        "metrics.control_readiness": test_ids,
                    },
                    "suite": {
                        "path": "tests/test_agent.py",
                        "sha256": suite_hash,
                    },
                    "metrics": {"control_readiness": 1.0},
                },
                indent=2,
            )
            + "\n"
        )
        return manifest_path

    def test_check_runs_from_an_external_project_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_active_component(root)

            result, output = self.run_cli(root, "check")

            self.assertEqual(0, result, output)
            self.assertIn("✓ 1 AI component found", output)
            self.assertIn("✓ 9 verified controls", output)
            self.assertIn("✓ 1 evaluation suite passed", output)
            self.assertTrue(output.rstrip().endswith("TRUST check passed"))

    def test_check_explains_a_stale_suite_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = self.write_active_component(root)
            manifest = json.loads(manifest_path.read_text())
            manifest["evaluation"]["suite"]["sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

            result, output = self.run_cli(root, "check")

            self.assertEqual(1, result, output)
            self.assertIn(
                "✗ agent: evaluation suite hash is stale; update the hash "
                "and result artifact",
                output,
            )
            self.assertTrue(output.rstrip().endswith("TRUST check failed"))


if __name__ == "__main__":
    unittest.main()

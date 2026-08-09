from __future__ import annotations

import json
import unittest
from pathlib import Path

from helpers import ROOT, load_module


trace = load_module("examples/traceability/correct.py", "example_trace")
graph = load_module(
    "examples/traceability/graphrag_correct.py", "example_graphrag"
)
resilience = load_module("examples/resilience/correct.py", "example_resilience")
utility = load_module("examples/unit-economics/correct.py", "example_utility")
structure = load_module("examples/state-structure/correct.py", "example_structure")
sandbox = load_module(
    "examples/state-structure/sandbox_correct.py", "example_sandbox"
)
support_answer = load_module(
    "examples/support-answer-generator/correct.py",
    "example_support_answer",
)
testability = load_module(
    "examples/testability/correct.py", "example_testability"
)


class TraceabilityTests(unittest.TestCase):
    def test_observable_call_is_reconstructable(self):
        artifacts = trace.ArtifactStore()
        traces = trace.TraceStore()
        client = trace.FakeSummarizer()
        result = trace.summarize_document(
            "A durable test document with enough words to create a concise summary.",
            client=client,
            artifacts=artifacts,
            traces=traces,
        )

        required = {
            "run_id",
            "component",
            "instruction_id",
            "instruction_artifact",
            "model_id",
            "input_artifact",
            "source_artifacts",
            "provider_request_id",
            "output_artifact",
            "status",
        }
        self.assertEqual(required, set(result["trace"]))
        self.assertEqual(
            result["summary"],
            artifacts.get(result["trace"]["output_artifact"]),
        )
        self.assertEqual(
            result["summary"],
            trace.replay_observable_call(
                result["trace"], client=client, artifacts=artifacts
            ),
        )

    def test_graphrag_trace_records_every_selected_edge(self):
        result = graph.answer_graph_query(
            "Which Acme subsidiaries operate in renewable energy?"
        )
        self.assertEqual("greenpower", result["answer"])
        self.assertEqual(len(graph.GRAPH), len(result["trace"]["hops"]))
        self.assertIn("greenpower", result["trace"]["answer_source_node_ids"])


class ResilienceTests(unittest.TestCase):
    def test_unsafe_primary_uses_valid_secondary(self):
        primary = resilience.FakeModelClient("primary", "import os\nos.remove('x')")
        secondary = resilience.FakeModelClient(
            "secondary", "def add(left, right):\n    return left + right\n"
        )
        result = resilience.generate_code(
            "add two values", primary=primary, secondary=secondary
        )
        self.assertEqual("secondary", result.route)
        self.assertTrue(result.degraded)
        self.assertIsNotNone(result.code)

    def test_exhaustion_is_explicit(self):
        primary = resilience.FakeModelClient(
            "primary", resilience.TemporaryModelError("outage")
        )
        secondary = resilience.FakeModelClient("secondary", "def broken(:")
        result = resilience.generate_code(
            "broken task", primary=primary, secondary=secondary
        )
        self.assertEqual("unavailable", result.route)
        self.assertIsNone(result.code)

    def test_unexpected_provider_error_uses_secondary(self):
        primary = resilience.FakeModelClient(
            "primary",
            RuntimeError("provider adapter failed"),
        )
        secondary = resilience.FakeModelClient(
            "secondary",
            "def available():\n    return True\n",
        )
        result = resilience.generate_code(
            "return availability",
            primary=primary,
            secondary=secondary,
        )
        self.assertEqual("secondary", result.route)
        self.assertTrue(result.degraded)

    def test_fallback_receives_only_remaining_total_budget(self):
        clock_values = iter((0.0, 0.0, 0.003))
        primary = resilience.FakeModelClient("primary", "def broken(:")
        secondary = resilience.FakeModelClient(
            "secondary",
            "def available():\n    return True\n",
        )
        result = resilience.generate_code(
            "return availability",
            primary=primary,
            secondary=secondary,
            timeout_ms=10,
            clock=lambda: next(clock_values),
        )
        self.assertEqual("secondary", result.route)
        self.assertEqual([10], primary.timeouts_ms)
        self.assertEqual([7], secondary.timeouts_ms)


class UtilityTests(unittest.TestCase):
    def make_service(self):
        generator = utility.FakeGenerator()
        service = utility.FAQService(
            faqs=utility.REFERENCE_FAQS,
            generator=generator,
            cache=utility.TTLCache(),
            policy_version="v2",
        )
        return service, generator

    def test_measured_reference_sequence(self):
        service, generator = self.make_service()
        questions = [
            "What is your return policy?",
            "What is your return policy?",
            "How long does shipping take?",
            "How long does shipping take?",
            "Which payment methods are accepted?",
            "your return policy",
            "how long shipping take",
            "payment methods accepted",
            "what about it",
            "Do you sell gift cards?",
        ]
        for index, question in enumerate(questions):
            service.answer(
                question, tenant_id="tenant-a", locale="en", now=index
            )
        self.assertEqual(2, generator.calls)

        expected = json.loads(
            (ROOT / "case-studies/results/faq-routing.json").read_text()
        )
        metrics = expected["metrics"]
        self.assertEqual(metrics["reference_router_calls"], generator.calls)
        self.assertEqual(
            metrics["generator_call_reduction"],
            (metrics["always_generate_calls"] - generator.calls)
            / metrics["always_generate_calls"],
        )

    def test_generated_answer_is_not_reused(self):
        service, generator = self.make_service()
        for now in (1, 2):
            service.answer(
                "Do you sell gift cards?",
                tenant_id="tenant-a",
                locale="en",
                now=now,
            )
        self.assertEqual(2, generator.calls)

    def test_reference_output_token_limit_is_enforced(self):
        self.assertEqual(
            "one two three",
            utility.truncate_reference_tokens("one two three four", 3),
        )


class SupportAnswerTests(unittest.TestCase):
    def test_answer_uses_only_approved_cited_sources(self):
        result = support_answer.answer_support_question(
            "What is the returns window?",
            articles=support_answer.REFERENCE_ARTICLES,
            client=support_answer.FakeAnswerClient(),
        )
        self.assertEqual(("kb-returns-v3",), result.cited_article_ids)
        self.assertNotIn("always free", result.text)

    def test_unsupported_question_abstains(self):
        result = support_answer.answer_support_question(
            "Do you provide aircraft maintenance?",
            articles=support_answer.REFERENCE_ARTICLES,
            client=support_answer.FakeAnswerClient(),
        )
        self.assertEqual((), result.cited_article_ids)
        self.assertEqual("No approved source supports an answer.", result.text)


class StructureTests(unittest.TestCase):
    def valid_payload(self):
        return {
            "title": "Senior Python Engineer",
            "salary_min": 100000,
            "salary_max": 130000,
            "location": "Berlin",
            "remote": True,
            "skills": ["Python"],
            "evidence": {
                "title": "Senior Python Engineer",
                "salary_min": "100000",
                "salary_max": "130000",
                "location": "Berlin",
                "remote": "Remote work is allowed",
                "skills": "Python",
            },
        }

    def test_invalid_relation_is_retried_before_return(self):
        document = (
            "Senior Python Engineer in Berlin. Salary 100000 to 130000 USD. "
            "Remote work is allowed."
        )
        invalid = self.valid_payload()
        invalid["salary_min"] = 140000
        client = structure.FakeStructuredClient([invalid, self.valid_payload()])
        result = structure.extract_job_data(document, client)
        self.assertEqual(100000, result.salary_min)
        self.assertLessEqual(result.salary_min, result.salary_max)

    def test_unresolved_evidence_is_blocked(self):
        payload = self.valid_payload()
        payload["evidence"]["location"] = "Paris"
        with self.assertRaises(structure.ValidationError):
            structure.validate_job_data(payload, "Senior Python Engineer in Berlin.")

    def test_empty_evidence_quote_is_blocked(self):
        payload = self.valid_payload()
        payload["evidence"]["title"] = ""
        with self.assertRaises(structure.ValidationError):
            structure.validate_job_data(payload, "Senior Python Engineer in Berlin.")


class SandboxTests(unittest.TestCase):
    def setUp(self):
        self.context = sandbox.IdentityContext(
            user_id="agent-operator",
            tenant_id="tenant-a",
            permitted_ticket_ids=frozenset({"ticket-1"}),
            can_route=True,
            can_notify=True,
        )
        self.store = sandbox.TicketStore(
            tickets={("tenant-a", "ticket-1"): {"queue": "unassigned"}}
        )
        self.valid_plan = sandbox.ActionPlan(
            next_state="done",
            calls=(
                sandbox.ToolCall(
                    "assign_to_queue",
                    {"ticket_id": "ticket-1", "queue": "billing-tier1"},
                ),
                sandbox.ToolCall(
                    "send_acknowledgement",
                    {"ticket_id": "ticket-1", "template": "routing-received"},
                ),
            ),
            idempotency_key="ticket-1:route:v1",
        )
        self.confirmation = sandbox.confirm_plan(self.valid_plan, self.context)

    def test_valid_plan_and_idempotent_replay(self):
        first = sandbox.execute_plan(
            self.valid_plan,
            contract=sandbox.ROUTE_CONTRACT,
            context=self.context,
            store=self.store,
            confirmation=self.confirmation,
        )
        second = sandbox.execute_plan(
            self.valid_plan,
            contract=sandbox.ROUTE_CONTRACT,
            context=self.context,
            store=self.store,
            confirmation=self.confirmation,
        )
        self.assertEqual("applied", first)
        self.assertEqual("already_applied", second)
        self.assertEqual(1, len(self.store.notifications))

    def test_fake_transaction_rolls_back_partial_effects(self):
        self.store.fail_on_tool = "send_acknowledgement"
        with self.assertRaises(RuntimeError):
            sandbox.execute_plan(
                self.valid_plan,
                contract=sandbox.ROUTE_CONTRACT,
                context=self.context,
                store=self.store,
                confirmation=self.confirmation,
            )
        self.assertEqual("unassigned", self.store.tickets[("tenant-a", "ticket-1")]["queue"])
        self.assertEqual([], self.store.notifications)
        self.assertEqual(set(), self.store.applied_keys)

    def test_idempotency_key_is_tenant_scoped(self):
        sandbox.execute_plan(
            self.valid_plan,
            contract=sandbox.ROUTE_CONTRACT,
            context=self.context,
            store=self.store,
            confirmation=self.confirmation,
        )
        self.store.tickets[("tenant-b", "ticket-1")] = {"queue": "unassigned"}
        second_context = sandbox.IdentityContext(
            user_id="agent-operator",
            tenant_id="tenant-b",
            permitted_ticket_ids=frozenset({"ticket-1"}),
            can_route=True,
            can_notify=True,
        )
        result = sandbox.execute_plan(
            self.valid_plan,
            contract=sandbox.ROUTE_CONTRACT,
            context=second_context,
            store=self.store,
            confirmation=sandbox.confirm_plan(self.valid_plan, second_context),
        )
        self.assertEqual("applied", result)
        self.assertEqual(2, len(self.store.notifications))

    def test_idempotency_key_is_bound_to_plan_payload(self):
        sandbox.execute_plan(
            self.valid_plan,
            contract=sandbox.ROUTE_CONTRACT,
            context=self.context,
            store=self.store,
            confirmation=self.confirmation,
        )
        conflicting = sandbox.ActionPlan(
            next_state="done",
            calls=(
                sandbox.ToolCall(
                    "assign_to_queue",
                    {"ticket_id": "ticket-1", "queue": "billing-tier2"},
                ),
            ),
            idempotency_key=self.valid_plan.idempotency_key,
        )
        with self.assertRaises(sandbox.IdempotencyConflict):
            sandbox.execute_plan(
                conflicting,
                contract=sandbox.ROUTE_CONTRACT,
                context=self.context,
                store=self.store,
                confirmation=sandbox.confirm_plan(conflicting, self.context),
            )

    def test_confirmation_is_bound_to_identity_tenant_and_plan(self):
        changed_plan = sandbox.ActionPlan(
            next_state="done",
            calls=(
                sandbox.ToolCall(
                    "assign_to_queue",
                    {"ticket_id": "ticket-1", "queue": "billing-tier2"},
                ),
            ),
            idempotency_key="ticket-1:route:v2",
        )
        with self.assertRaises(sandbox.AuthorizationDenied):
            sandbox.execute_plan(
                changed_plan,
                contract=sandbox.ROUTE_CONTRACT,
                context=self.context,
                store=self.store,
                confirmation=self.confirmation,
            )

    def test_control_events_are_audited_and_alerted(self):
        result = sandbox.execute_plan(
            self.valid_plan,
            contract=sandbox.ROUTE_CONTRACT,
            context=self.context,
            store=self.store,
            confirmation=self.confirmation,
        )
        self.assertEqual("applied", result)
        self.assertEqual("applied", self.store.audit_events[-1]["outcome"])
        self.assertEqual([], self.store.alert_signals)
        self.assertNotIn("arguments", self.store.audit_events[-1])

        changed_plan = sandbox.ActionPlan(
            next_state="done",
            calls=self.valid_plan.calls,
            idempotency_key="ticket-1:route:v2",
        )
        with self.assertRaises(sandbox.AuthorizationDenied):
            sandbox.execute_plan(
                changed_plan,
                contract=sandbox.ROUTE_CONTRACT,
                context=self.context,
                store=self.store,
                confirmation=self.confirmation,
            )
        self.assertEqual("blocked_plan", self.store.audit_events[-1]["outcome"])
        self.assertEqual("blocked_plan", self.store.alert_signals[-1]["outcome"])

    def test_four_adversarial_plans_are_blocked_before_effects(self):
        attacks = [
            (self.valid_plan, None),
            sandbox.ActionPlan(
                    "done",
                    (
                        sandbox.ToolCall(
                            "assign_to_queue",
                            {"ticket_id": "ticket-2", "queue": "billing-tier1"},
                        ),
                    ),
                    "unauthorized",
            ),
            sandbox.ActionPlan(
                    "done",
                    (
                        sandbox.ToolCall(
                            "assign_to_queue",
                            {"ticket_id": "ticket-1", "queue": "billing-tier1"},
                        ),
                        sandbox.ToolCall(
                            "assign_to_queue",
                            {"ticket_id": "ticket-1", "queue": "billing-tier2"},
                        ),
                    ),
                    "too-many",
            ),
            sandbox.ActionPlan(
                    "done",
                    (
                        sandbox.ToolCall(
                            "delete_ticket", {"ticket_id": "ticket-1"}
                        ),
                    ),
                    "forbidden",
            ),
        ]
        blocked = 0
        for item in attacks:
            if isinstance(item, tuple):
                plan, confirmation = item
            else:
                plan = item
                confirmation = sandbox.confirm_plan(plan, self.context)
            before = (
                dict(self.store.tickets),
                list(self.store.notifications),
            )
            with self.assertRaises((sandbox.ContractViolation, sandbox.AuthorizationDenied)):
                sandbox.execute_plan(
                    plan,
                    contract=sandbox.ROUTE_CONTRACT,
                    context=self.context,
                    store=self.store,
                    confirmation=confirmation,
                )
            self.assertEqual(before[0], self.store.tickets)
            self.assertEqual(before[1], self.store.notifications)
            blocked += 1

        expected = json.loads(
            (ROOT / "case-studies/results/agentic-control.json").read_text()
        )
        self.assertEqual(
            expected["metrics"]["unauthorized_action_block_rate"],
            blocked / len(attacks),
        )
        self.assertEqual(1.0, blocked / len(attacks))


class TestabilityTests(unittest.TestCase):
    def test_candidate_passes_predeclared_gate(self):
        cases = testability.load_cases(ROOT / "evals/support-triage-v1.jsonl")
        baseline = testability.run_offline_eval(
            testability.BaselineClassifier(), cases, blocking_accuracy=0.9
        )
        candidate = testability.run_offline_eval(
            testability.CandidateClassifier(), cases, blocking_accuracy=0.9
        )
        expected = json.loads(
            (ROOT / "case-studies/results/support-triage.json").read_text()
        )
        metrics = expected["metrics"]
        self.assertEqual(metrics["baseline"]["accuracy"], baseline["accuracy"])
        self.assertEqual(metrics["candidate"]["accuracy"], candidate["accuracy"])
        self.assertFalse(baseline["passed"])
        self.assertTrue(candidate["passed"])

    def test_unknown_abstains(self):
        result = testability.route_ticket(
            testability.CandidateClassifier(), "please help me again"
        )
        self.assertEqual({"status": "manual_review", "queue": None}, result)


if __name__ == "__main__":
    unittest.main()

"""Executable reference: versioned offline evaluation for support triage.

This replaces the former medical example. Metrics are measured on a committed
synthetic fixture and must not be represented as production performance.

Guarantees:
- baseline and candidate run on the same versioned cases;
- the blocking threshold is predeclared;
- unknown cases abstain to manual review.

Does not guarantee production representativeness, fairness, or calibrated model
confidence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class TicketPrediction:
    queue: str
    review_required: bool


@dataclass(frozen=True)
class EvalCase:
    text: str
    expected_queue: str
    review_required: bool


class Classifier(Protocol):
    version: str

    def classify(self, text: str) -> TicketPrediction:
        ...


class BaselineClassifier:
    version = "support-triage:baseline-v1"

    def classify(self, text: str) -> TicketPrediction:
        lowered = text.lower()
        if any(word in lowered for word in ("charged", "refund")):
            return TicketPrediction("billing", False)
        if any(word in lowered for word in ("crash", "error")):
            return TicketPrediction("technical", False)
        return TicketPrediction("unknown", True)


class CandidateClassifier:
    version = "support-triage:candidate-v2"

    def classify(self, text: str) -> TicketPrediction:
        lowered = text.lower()
        rules = {
            "billing": ("charged", "refund"),
            "technical": ("crash", "error"),
            "account": ("login", "email"),
            "shipping": ("tracking", "package"),
        }
        matches = [
            queue
            for queue, keywords in rules.items()
            if any(keyword in lowered for keyword in keywords)
        ]
        if len(matches) != 1:
            return TicketPrediction("unknown", True)
        return TicketPrediction(matches[0], False)


def load_cases(path: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        cases.append(
            EvalCase(
                text=raw["text"],
                expected_queue=raw["expected_queue"],
                review_required=raw["review_required"],
            )
        )
    if not cases:
        raise ValueError("evaluation suite must not be empty")
    return cases


def run_offline_eval(
    classifier: Classifier,
    cases: list[EvalCase],
    *,
    blocking_accuracy: float,
) -> dict:
    correct = 0
    review_correct = 0
    rows: list[dict] = []
    for case in cases:
        prediction = classifier.classify(case.text)
        correct += prediction.queue == case.expected_queue
        review_correct += prediction.review_required == case.review_required
        rows.append(
            {
                "expected": case.expected_queue,
                "predicted": prediction.queue,
                "review_expected": case.review_required,
                "review_predicted": prediction.review_required,
            }
        )

    accuracy = correct / len(cases)
    review_policy_accuracy = review_correct / len(cases)
    return {
        "classifier_version": classifier.version,
        "suite_size": len(cases),
        "accuracy": accuracy,
        "review_policy_accuracy": review_policy_accuracy,
        "blocking_accuracy": blocking_accuracy,
        "passed": accuracy >= blocking_accuracy and review_policy_accuracy == 1.0,
        "rows": rows,
    }


def route_ticket(classifier: Classifier, text: str) -> dict:
    prediction = classifier.classify(text)
    if prediction.review_required:
        return {"status": "manual_review", "queue": None}
    return {"status": "proposed", "queue": prediction.queue}

# Testability — Correct Implementation
# Scenario: Deploying a new prompt for medical symptom triage

import json
import structlog
import openai
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

client = openai.OpenAI()
logger = structlog.get_logger()

PROMPT_VERSION = "triage_v3.2.0"
SYSTEM_PROMPT = Path(f"prompts/{PROMPT_VERSION}.txt").read_text()

# ✅ Confidence threshold below which the case goes to a human.
#    This value is derived from eval results, not guesswork.
HITL_CONFIDENCE_THRESHOLD = 0.75


class TriageLevel(str, Enum):
    EMERGENCY = "emergency"
    URGENT_CARE = "urgent_care"
    SELF_CARE = "self_care"
    UNKNOWN = "unknown"


@dataclass
class TriageResult:
    level: TriageLevel
    reasoning: str
    confidence: float
    escalated_to_human: bool
    prompt_version: str


# ─── OFFLINE EVALUATION (run in CI before every deploy) ──────────────────────

@dataclass
class EvalCase:
    symptoms: str
    expected_level: TriageLevel
    is_safety_critical: bool  # failures here are blocking, not just regressions


GOLDEN_DATASET: list[EvalCase] = [
    # Safety-critical: these MUST be classified as EMERGENCY
    EvalCase("crushing chest pain radiating to left arm, sweating", TriageLevel.EMERGENCY, True),
    EvalCase("difficulty breathing, lips turning blue", TriageLevel.EMERGENCY, True),
    EvalCase("sudden severe headache, worst of my life", TriageLevel.EMERGENCY, True),
    EvalCase("unconscious, not breathing", TriageLevel.EMERGENCY, True),

    # Urgent care cases
    EvalCase("high fever 103F for two days, not improving", TriageLevel.URGENT_CARE, False),
    EvalCase("deep cut that may need stitches, bleeding controlled", TriageLevel.URGENT_CARE, False),

    # Self-care cases
    EvalCase("mild sore throat, runny nose, no fever", TriageLevel.SELF_CARE, False),
    EvalCase("muscle soreness after workout", TriageLevel.SELF_CARE, False),

    # Edge cases — model should express low confidence, not guess
    EvalCase("I feel weird", TriageLevel.UNKNOWN, False),
    EvalCase("stomach hurts a little sometimes", TriageLevel.UNKNOWN, False),
]


def run_offline_eval(dataset: list[EvalCase] = GOLDEN_DATASET) -> dict:
    """
    ✅ Run before every deploy. Returns pass/fail + metrics.
    In CI: assert results["passed"], results["failure_reason"]
    """
    results = {"total": len(dataset), "correct": 0, "safety_failures": [], "regressions": []}

    for case in dataset:
        result = _call_triage_model(case.symptoms)

        if result.level == case.expected_level:
            results["correct"] += 1
        else:
            entry = {"symptoms": case.symptoms, "expected": case.expected_level, "got": result.level}
            if case.is_safety_critical:
                # ✅ Safety-critical misclassifications are blocking — deploy cannot proceed.
                results["safety_failures"].append(entry)
            else:
                results["regressions"].append(entry)

    results["accuracy"] = results["correct"] / results["total"]
    results["safety_passed"] = len(results["safety_failures"]) == 0

    # ✅ Thresholds defined before seeing results — not adjusted post-hoc.
    results["passed"] = (
        results["safety_passed"] and          # zero tolerance on safety
        results["accuracy"] >= 0.90            # 90% overall accuracy required
    )

    if not results["passed"]:
        if not results["safety_passed"]:
            results["failure_reason"] = f"SAFETY FAILURE: {results['safety_failures']}"
        else:
            results["failure_reason"] = f"Accuracy {results['accuracy']:.1%} below threshold 90%"

    return results


# ─── PRODUCTION INFERENCE ────────────────────────────────────────────────────

def _call_triage_model(symptoms: str) -> TriageResult:
    """Raw model call — returns structured result with confidence."""
    response = client.chat.completions.create(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Symptoms: {symptoms}\n\nRespond with JSON: {{\"level\": \"emergency|urgent_care|self_care|unknown\", \"reasoning\": \"...\", \"confidence\": 0.0-1.0}}"
            },
        ],
        response_format={"type": "json_object"},
        max_tokens=300,
        temperature=0,
    )

    data = json.loads(response.choices[0].message.content)
    return TriageResult(
        level=TriageLevel(data.get("level", "unknown")),
        reasoning=data.get("reasoning", ""),
        confidence=float(data.get("confidence", 0.5)),
        escalated_to_human=False,
        prompt_version=PROMPT_VERSION,
    )


def triage_symptoms(symptoms: str, session_id: Optional[str] = None) -> TriageResult:
    """
    ✅ Production triage with HITL escalation for low-confidence cases.
    """
    result = _call_triage_model(symptoms)

    # ✅ HITL escalation: low confidence goes to a human operator.
    #    High-stakes domain (medical) — uncertainty is not passed through silently.
    if result.confidence < HITL_CONFIDENCE_THRESHOLD or result.level == TriageLevel.UNKNOWN:
        result.escalated_to_human = True
        _escalate_to_human(session_id, symptoms, result)

    # ✅ Log everything for online metric tracking.
    logger.info(
        "triage_complete",
        level=result.level,
        confidence=result.confidence,
        escalated=result.escalated_to_human,
        prompt_version=result.prompt_version,
    )

    return result


def _escalate_to_human(session_id: Optional[str], symptoms: str, result: TriageResult):
    """Route to human operator queue. Implementation depends on your stack."""
    logger.warning(
        "triage_escalated_to_human",
        session_id=session_id,
        confidence=result.confidence,
        model_suggestion=result.level,
    )
    # → push to human review queue, notify on-call, etc.


# ─── USAGE ───────────────────────────────────────────────────────────────────

# Before deploying a new prompt version:
#
#   results = run_offline_eval()
#   assert results["passed"], results.get("failure_reason")
#
# In CI/CD:
#
#   pytest tests/test_triage_eval.py   ← runs run_offline_eval() as a test
#
# Online monitoring (in your metrics dashboard):
#
#   alert if escalation_rate > 15% over 30 min  → prompt may have regressed
#   alert if emergency_rate drops suddenly       → safety regression in prod
#   alert if confidence_p50 drops below 0.80     → distribution shift

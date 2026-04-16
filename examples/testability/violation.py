# Testability — Violation
# Scenario: Deploying a new prompt for medical symptom triage

import openai

client = openai.OpenAI()

# ❌ The old prompt. Changed to the new one because "it felt better."
# SYSTEM_PROMPT = "You are a medical triage assistant..."

# ❌ New prompt deployed directly to production.
#    No eval was run. No metric was measured.
#    "I tested a few examples by hand and it seemed fine."
SYSTEM_PROMPT = """You are an experienced medical triage assistant.
Your job is to assess symptom severity and recommend the appropriate
level of care: emergency, urgent care, or self-care.
Be empathetic and clear."""


def triage_symptoms(symptoms: str) -> dict:
    response = client.chat.completions.create(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": symptoms},
        ],
    )

    recommendation = response.choices[0].message.content

    # ❌ No confidence scoring. All outputs are treated as equally reliable.
    #    A response about chest pain gets the same handling as a question about a cold.
    #    No HITL escalation for ambiguous or high-stakes cases.
    return {"recommendation": recommendation}


# ❌ What happened in practice:
#
# The new prompt was more empathetic but occasionally said "this could be serious,
# you might want to consider urgent care" for clearly emergency symptoms like
# "crushing chest pain and left arm numbness."
#
# This was a regression. Nobody caught it because:
# - No golden dataset existed
# - No eval was run
# - No metric was defined
# - No monitoring existed in production
# - The first signal was a user complaint, two weeks later

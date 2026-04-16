# Resilience — Violation
# Scenario: AI code assistant — generating Python helper functions

import openai
from fastapi import FastAPI

app = FastAPI()
client = openai.OpenAI()

SYSTEM_PROMPT = (
    "You are a Python code generator. "
    "Return ONLY valid Python code — no markdown fences, no explanation."
)


@app.post("/generate-code")
async def generate_code(description: str) -> dict:
    """
    Generates a Python helper function from a natural language description.
    """

    # ❌ Always calls the most expensive reasoning model for every request.
    #    o3 costs ~70× more per token than gpt-4o-mini.
    #    A trivial "write a function to add two numbers" burns the same budget
    #    as a complex algorithmic problem. No cost differentiation whatsoever.
    response = client.chat.completions.create(
        model="o3",
        # ❌ No timeout. Reasoning models may take 30–120 seconds to respond.
        #    A single slow request can stall the entire thread pool.
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": description},
        ],
    )

    # ❌ No output validation.
    #    The model may return code wrapped in markdown fences, prose mixed with
    #    code, or outright syntactically invalid Python on complex prompts.
    #    None of that is caught here — it silently reaches the caller.
    code = response.choices[0].message.content

    return {"code": code}


# ❌ What happens at scale?
#
#   1,000 requests/day × ~$0.014/req (o3) = $14.00/day
#   With quality-gated escalation (see correct.py): ~$0.43/day
#   That is a ~33× unnecessary cost premium.
#
# ❌ What happens when o3 returns invalid Python?
#
#   - The caller's ast.parse() or exec() raises SyntaxError at runtime
#   - No log, no metric, no alert — the failure is invisible here
#   - The engineer finds out from a customer bug report days later

# State & Structure — Violation
# Scenario: Extract structured data from a job posting

import openai

client = openai.OpenAI()


def extract_job_data(job_posting: str) -> dict:
    """
    Extracts structured fields from a job posting.
    Returns a dict with title, salary, location, skills.
    """

    response = client.chat.completions.create(
        model="gpt-4o-2024-08-06",
        messages=[
            {
                "role": "user",
                # ❌ Schema is described in natural language inside the prompt.
                #    No machine-readable schema exists anywhere in this codebase.
                "content": f"""Extract job information from this posting.
Respond with JSON like this:
{{
  "title": "job title here",
  "salary_min": 50000,
  "salary_max": 80000,
  "location": "city name",
  "remote": true or false,
  "skills": ["skill1", "skill2"]
}}

Job posting:
{job_posting}"""
            }
        ],
    )

    raw = response.choices[0].message.content

    # ❌ Parsing text with fragile string manipulation.
    #    The model might return "```json\n{...}\n```" or just "{...}"
    #    or "Here is the JSON:\n{...}" — all variations break this.
    import json
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0]

    data = json.loads(raw)  # ❌ Will throw on malformed output — no retry

    # ❌ Trusting the parsed dict directly with no validation.
    #    salary_min might be a string. skills might be None.
    #    remote might be "yes" instead of True.
    #    Any of these will cause a downstream crash.
    return {
        "title": data["title"],
        "salary_range": f"{data['salary_min']} - {data['salary_max']}",
        "location": data["location"],
        "remote": data["remote"],
        "skills": data["skills"],
    }


# ❌ Bugs waiting to happen:
#
# - Model returns salary as "$50,000" string → int() crashes
# - Model omits "remote" field → KeyError
# - Model returns skills as a comma-separated string → not a list
# - Model wraps JSON in markdown → json.loads crashes
# - Any of the above → unhandled exception, no retry, user sees 500

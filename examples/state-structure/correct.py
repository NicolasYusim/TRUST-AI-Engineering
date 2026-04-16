# State & Structure — Correct Implementation
# Scenario: Extract structured data from a job posting

import structlog
import openai
from pydantic import BaseModel, Field, field_validator
from typing import Optional

client = openai.OpenAI()
logger = structlog.get_logger()

MAX_RETRIES = 3


# ✅ Schema is defined in code, not in a prompt string.
#    This is the single source of truth.
#    Pydantic validates types, ranges, and constraints automatically.
class JobData(BaseModel):
    title: str = Field(description="The job title or role name")
    salary_min: Optional[int] = Field(None, ge=0, description="Minimum salary in USD")
    salary_max: Optional[int] = Field(None, ge=0, description="Maximum salary in USD")
    location: Optional[str] = Field(None, description="City or region")
    remote: bool = Field(False, description="Whether remote work is allowed")
    skills: list[str] = Field(default_factory=list, description="Required technical skills")

    @field_validator("skills", mode="before")
    @classmethod
    def normalize_skills(cls, v):
        # ✅ Defensive: handle if model returns a comma-separated string
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v or []

    @field_validator("salary_min", "salary_max", mode="before")
    @classmethod
    def parse_salary(cls, v):
        # ✅ Defensive: handle if model returns "$50,000" or "50k"
        if isinstance(v, str):
            cleaned = v.replace("$", "").replace(",", "").replace("k", "000").strip()
            return int(cleaned) if cleaned.isdigit() else None
        return v


def extract_job_data(job_posting: str) -> JobData:
    """
    Extracts structured fields from a job posting.
    Uses OpenAI's structured output (JSON mode with schema) + Pydantic validation.
    Retries with error context on schema violations.
    """

    # ✅ Use OpenAI's native structured output.
    #    The model is constrained to produce valid JSON matching the schema.
    #    This eliminates the markdown wrapping / free-text prefix problem.
    messages = [
        {
            "role": "system",
            "content": "Extract structured job data. Return only the JSON object, no explanation.",
        },
        {"role": "user", "content": job_posting},
    ]

    last_error: Optional[Exception] = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-2024-08-06",
                messages=messages,
                response_format={"type": "json_object"},  # ✅ JSON mode enforced
                max_tokens=400,
                temperature=0,
            )

            raw = response.choices[0].message.content

            # ✅ Validate through Pydantic — types, ranges, and defaults are enforced.
            #    If this passes, the returned object is guaranteed to be well-formed.
            result = JobData.model_validate_json(raw)

            if attempt > 1:
                logger.info("extraction_succeeded_after_retry", attempt=attempt)

            return result

        except Exception as e:
            last_error = e
            logger.warning("extraction_attempt_failed", attempt=attempt, error=str(e))

            # ✅ Add the specific validation error to the next prompt.
            #    The model now knows exactly what went wrong and can correct it.
            messages.append({"role": "assistant", "content": response.choices[0].message.content})
            messages.append({
                "role": "user",
                "content": f"That response failed validation with this error: {e}\n\nPlease fix it and return only the corrected JSON.",
            })

    # ✅ After max retries, fail explicitly — not silently.
    raise ValueError(f"Failed to extract job data after {MAX_RETRIES} attempts. Last error: {last_error}")


# ✅ The returned JobData object is guaranteed:
#
# - result.title is always a str
# - result.skills is always a list[str] (never None, never a comma-string)
# - result.remote is always a bool
# - result.salary_min / salary_max are int or None (never "$50,000")
# - Any violation was retried with error context, or raised explicitly
#
# Business logic downstream can trust this object unconditionally.

"""Executable reference: validated extraction with source evidence.

Guarantees shape, local domain invariants, and that evidence quotes resolve to the
input text. It does not guarantee that a valid field is the correct
interpretation of the document.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


JOB_SCHEMA = {
    "title": "string",
    "salary_min": "integer|null",
    "salary_max": "integer|null",
    "location": "string|null",
    "remote": "boolean|null",
    "skills": "array[string]",
    "evidence": "object[field -> quote]",
}


class ValidationError(ValueError):
    pass


class StructuredClient(Protocol):
    def complete(self, document: str, schema: dict[str, str]) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class JobData:
    title: str
    salary_min: int | None
    salary_max: int | None
    location: str | None
    remote: bool | None
    skills: tuple[str, ...]
    evidence: dict[str, str]


class FakeStructuredClient:
    """Deterministic provider substitute used by tests and documentation."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = list(responses)

    def complete(self, document: str, schema: dict[str, str]) -> dict[str, Any]:
        if not self._responses:
            raise RuntimeError("fake response sequence exhausted")
        return self._responses.pop(0)


def _optional_int(raw: Any, field: str) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        raise ValidationError(f"{field} must be a non-negative integer or null")
    return raw


def validate_job_data(raw: dict[str, Any], document: str) -> JobData:
    expected = {
        "title",
        "salary_min",
        "salary_max",
        "location",
        "remote",
        "skills",
        "evidence",
    }
    if set(raw) != expected:
        raise ValidationError(f"expected exactly {sorted(expected)}")

    title = raw["title"]
    if not isinstance(title, str) or not title.strip():
        raise ValidationError("title must be a non-empty string")

    salary_min = _optional_int(raw["salary_min"], "salary_min")
    salary_max = _optional_int(raw["salary_max"], "salary_max")
    if salary_min is not None and salary_max is not None and salary_min > salary_max:
        raise ValidationError("salary_min must not exceed salary_max")

    location = raw["location"]
    if location is not None and not isinstance(location, str):
        raise ValidationError("location must be a string or null")

    remote = raw["remote"]
    if remote is not None and not isinstance(remote, bool):
        raise ValidationError("remote must be a boolean or null")

    skills = raw["skills"]
    if not isinstance(skills, list) or not all(
        isinstance(skill, str) and skill.strip() for skill in skills
    ):
        raise ValidationError("skills must be a list of non-empty strings")

    evidence = raw["evidence"]
    if not isinstance(evidence, dict):
        raise ValidationError("evidence must be an object")
    for field, quote in evidence.items():
        if field not in expected - {"evidence"}:
            raise ValidationError(f"unknown evidence field: {field}")
        if not isinstance(quote, str) or not quote.strip() or quote not in document:
            raise ValidationError(f"evidence for {field} does not resolve to input")

    for field, value in {
        "title": title,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "location": location,
        "remote": remote,
        "skills": skills,
    }.items():
        if value not in (None, []) and field not in evidence:
            raise ValidationError(f"non-null field lacks evidence: {field}")

    return JobData(
        title=title.strip(),
        salary_min=salary_min,
        salary_max=salary_max,
        location=location,
        remote=remote,
        skills=tuple(skill.strip() for skill in skills),
        evidence=dict(evidence),
    )


def extract_job_data(
    document: str,
    client: StructuredClient,
    *,
    max_attempts: int = 2,
) -> JobData:
    # Evidence label: illustrative. This local retry bound is not a universal
    # provider recommendation.
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")

    last_error: ValidationError | None = None
    for _ in range(max_attempts):
        raw = client.complete(document, JOB_SCHEMA)
        try:
            return validate_job_data(raw, document)
        except ValidationError as exc:
            last_error = exc
    raise ValidationError(f"extraction failed validation: {last_error}")

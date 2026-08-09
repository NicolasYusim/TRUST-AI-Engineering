"""Executable reference: bounded FAQ routing and tenant-safe caching.

Guarantees:
- exact and high-similarity published FAQ matches avoid generation;
- reusable cache keys include tenant, locale, and policy version;
- context-dependent questions bypass reusable cache;
- generated answers are not cached as authoritative policy.

Does not guarantee semantic correctness of the illustrative token similarity or
establish a universal similarity threshold.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class FAQ:
    question: str
    answer: str
    policy_version: str


@dataclass(frozen=True)
class Answer:
    text: str
    source: str
    source_question: str | None = None


class Generator(Protocol):
    def answer(
        self,
        question: str,
        context: tuple[FAQ, ...],
        output_token_limit: int,
    ) -> str:
        ...


@dataclass
class FakeGenerator:
    calls: int = 0

    def answer(
        self,
        question: str,
        context: tuple[FAQ, ...],
        output_token_limit: int,
    ) -> str:
        self.calls += 1
        if not context:
            return "No published FAQ supports this answer."
        generated = f"Based on the published FAQ: {context[0].answer}"
        return truncate_reference_tokens(generated, output_token_limit)


@dataclass
class CacheEntry:
    answer: Answer
    expires_at: int


@dataclass
class TTLCache:
    entries: dict[tuple[str, str, str, str], CacheEntry] = field(default_factory=dict)

    def get(self, key: tuple[str, str, str, str], now: int) -> Answer | None:
        entry = self.entries.get(key)
        if entry is None or entry.expires_at <= now:
            self.entries.pop(key, None)
            return None
        return entry.answer

    def put(
        self,
        key: tuple[str, str, str, str],
        answer: Answer,
        *,
        now: int,
        ttl_seconds: int,
    ) -> None:
        self.entries[key] = CacheEntry(answer=answer, expires_at=now + ttl_seconds)


TOKEN_RE = re.compile(r"[a-z0-9]+")
CONTEXT_MARKERS = frozenset(
    {"it", "this", "that", "they", "them", "those", "previous", "again"}
)


def normalize(text: str) -> str:
    return " ".join(TOKEN_RE.findall(text.lower()))


def token_similarity(left: str, right: str) -> float:
    left_tokens = set(TOKEN_RE.findall(left.lower()))
    right_tokens = set(TOKEN_RE.findall(right.lower()))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def is_context_dependent(question: str) -> bool:
    return bool(set(TOKEN_RE.findall(question.lower())) & CONTEXT_MARKERS)


def truncate_reference_tokens(text: str, limit: int) -> str:
    """Apply the example's deterministic whitespace-token contract."""

    if limit < 1:
        raise ValueError("token limit must be positive")
    return " ".join(text.split()[:limit])


@dataclass
class FAQService:
    faqs: tuple[FAQ, ...]
    generator: Generator
    cache: TTLCache
    policy_version: str
    # Evidence label: illustrative. Calibrate on a versioned routing suite.
    similarity_threshold: float = 0.5
    # Evidence label: illustrative. Derive from policy freshness requirements.
    cache_ttl_seconds: int = 3600
    # Evidence label: illustrative. Production uses the provider tokenizer.
    output_token_limit: int = 160

    def answer(
        self,
        question: str,
        *,
        tenant_id: str,
        locale: str,
        now: int,
    ) -> Answer:
        standalone = not is_context_dependent(question)
        key = (tenant_id, locale, self.policy_version, normalize(question))
        if standalone:
            cached = self.cache.get(key, now)
            if cached is not None:
                return Answer(cached.text, "validated_cache", cached.source_question)

        current = tuple(
            faq for faq in self.faqs if faq.policy_version == self.policy_version
        )
        normalized = normalize(question)
        for faq in current:
            if normalize(faq.question) == normalized:
                answer = Answer(faq.answer, "exact_published_faq", faq.question)
                if standalone:
                    self.cache.put(
                        key, answer, now=now, ttl_seconds=self.cache_ttl_seconds
                    )
                return answer

        ranked = sorted(
            (
                (token_similarity(question, faq.question), faq)
                for faq in current
            ),
            key=lambda item: item[0],
            reverse=True,
        )
        if standalone and ranked and ranked[0][0] >= self.similarity_threshold:
            faq = ranked[0][1]
            answer = Answer(faq.answer, "semantic_published_faq", faq.question)
            self.cache.put(key, answer, now=now, ttl_seconds=self.cache_ttl_seconds)
            return answer

        context = tuple(faq for score, faq in ranked[:2] if score > 0)
        generated = self.generator.answer(
            question,
            context,
            self.output_token_limit,
        )
        # Generated output is deliberately not placed in the reusable cache.
        return Answer(generated, "generated_unverified")


REFERENCE_FAQS = (
    FAQ("What is your return policy?", "Returns are accepted for 30 days.", "v2"),
    FAQ("How long does shipping take?", "Shipping takes 3–5 business days.", "v2"),
    FAQ("Which payment methods are accepted?", "Cards and bank transfer.", "v2"),
)

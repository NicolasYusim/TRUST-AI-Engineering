"""Executable reference: cited support answers from approved knowledge only.

Guarantees that generation sees only approved matching articles, citations refer
to those articles, and unsupported questions abstain. It does not establish
semantic answer quality on a production support corpus.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol


TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class Article:
    article_id: str
    text: str
    approved: bool


@dataclass(frozen=True)
class GeneratedAnswer:
    text: str
    cited_article_ids: tuple[str, ...]


class AnswerClient(Protocol):
    def complete(
        self,
        question: str,
        articles: tuple[Article, ...],
        output_token_limit: int,
    ) -> GeneratedAnswer:
        ...


class FakeAnswerClient:
    def complete(
        self,
        question: str,
        articles: tuple[Article, ...],
        output_token_limit: int,
    ) -> GeneratedAnswer:
        article = articles[0]
        text = " ".join(article.text.split()[:output_token_limit])
        return GeneratedAnswer(text, (article.article_id,))


def _score(question: str, article: Article) -> int:
    question_tokens = set(TOKEN_RE.findall(question.lower()))
    article_tokens = set(TOKEN_RE.findall(article.text.lower()))
    return len(question_tokens & article_tokens)


def answer_support_question(
    question: str,
    *,
    articles: tuple[Article, ...],
    client: AnswerClient,
    output_token_limit: int = 400,
) -> GeneratedAnswer:
    if output_token_limit < 1:
        raise ValueError("output_token_limit must be positive")

    ranked = sorted(
        (
            (_score(question, article), article)
            for article in articles
            if article.approved
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    selected = tuple(article for score, article in ranked[:3] if score > 0)
    if not selected:
        return GeneratedAnswer(
            "No approved source supports an answer.",
            (),
        )

    generated = client.complete(question, selected, output_token_limit)
    selected_ids = {article.article_id for article in selected}
    if not generated.cited_article_ids:
        raise ValueError("generated answer must cite an approved source")
    if not set(generated.cited_article_ids) <= selected_ids:
        raise ValueError("generated answer cites a source outside approved context")
    if len(generated.text.split()) > output_token_limit:
        raise ValueError("generated answer exceeds output token limit")
    return generated


REFERENCE_ARTICLES = (
    Article(
        "kb-returns-v3",
        "Returns are accepted within 30 days when the item is unused.",
        True,
    ),
    Article(
        "draft-secret-policy",
        "Unapproved draft: returns are always free without conditions.",
        False,
    ),
)

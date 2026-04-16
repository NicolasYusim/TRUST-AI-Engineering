# Unit Economics — Correct Implementation
# Scenario: FAQ chatbot for an e-commerce platform

import hashlib
import re
import openai
import numpy as np
import structlog
from dataclasses import dataclass
from typing import Optional

client = openai.OpenAI()
logger = structlog.get_logger()

FAQ_DATABASE = [
    {"q": "What is your return policy?", "a": "30 days, no questions asked."},
    {"q": "How long does shipping take?", "a": "3-5 business days."},
    # ... 198 more entries
]

# ✅ Pre-compute embeddings for all FAQ questions once at startup.
#    In production: store in a vector DB (Pinecone, pgvector, etc.)
faq_embeddings: list[np.ndarray] = []  # populated at startup


@dataclass
class FAQResult:
    answer: str
    source: str  # "exact_cache" | "semantic_match" | "ai_generated"
    input_tokens: int = 0
    output_tokens: int = 0


# ✅ In-memory exact-match cache keyed by question hash.
#    In production: Redis with TTL aligned to FAQ update frequency.
_exact_cache: dict[str, str] = {}

# Anaphoric tokens that signal context-dependence: these questions reference
# a prior turn and cannot be answered from a stateless FAQ cache.
CONTEXT_SENSITIVE_SIGNALS = frozenset({
    "it", "its", "this", "that", "these", "those",
    "they", "them", "their",
    "he", "she", "him", "her",
    "the order", "the item", "the product", "the package",
})

# ✅ Regex patterns for policy topics that change infrequently.
#    Answers matching these topics are candidates for longer cache TTLs.
_STABLE_POLICY_RE = re.compile(
    r"\b(return policy|shipping|delivery|payment method|warranty|guarantee)\b",
    re.IGNORECASE,
)


def _cache_key(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode()).hexdigest()


def _semantic_search(query: str, top_k: int = 3) -> tuple[list[dict], np.ndarray]:
    """Find the most relevant FAQ entries using embedding similarity.

    Returns a tuple of:
    - matched FAQ entries, each augmented with its precomputed embedding
      under the key ``"emb"`` so callers can do a second similarity check
      without re-fetching from the vector store;
    - the query embedding, for reuse downstream (avoids a second API call).
    """
    query_emb = np.array(client.embeddings.create(
        model="text-embedding-3-small",   # ✅ Cheapest embedding model, sufficient for this
        input=query,
    ).data[0].embedding)

    scores = [
        np.dot(query_emb, faq_emb) for faq_emb in faq_embeddings
    ]
    top_indices = np.argsort(scores)[-top_k:][::-1]
    # ✅ Attach the precomputed FAQ embedding so _is_high_confidence_match
    #    can run cosine similarity without an extra vector-store lookup.
    results = [
        {**FAQ_DATABASE[i], "emb": faq_embeddings[i]}
        for i in top_indices if scores[i] > 0.82
    ]
    return results, query_emb


def answer_faq(user_question: str) -> FAQResult:
    # ✅ Layer 1: Exact cache — zero tokens, zero cost.
    #    Repeated questions (very common in FAQ scenarios) are free.
    key = _cache_key(user_question)
    if cached := _exact_cache.get(key):
        logger.info("faq_served", source="exact_cache")
        return FAQResult(answer=cached, source="exact_cache")

    # ✅ Layer 2: Semantic retrieval — find relevant FAQs first.
    #    Instead of injecting 200 entries, we inject only 1-3 relevant ones.
    #    Context shrinks from ~40,000 tokens to ~300 tokens.
    relevant_faqs, query_emb = _semantic_search(user_question)

    if len(relevant_faqs) == 1 and _is_high_confidence_match(relevant_faqs[0], query_emb):
        # ✅ High-confidence match: return the FAQ answer directly.
        #    No AI call needed at all for clear matches.
        answer = relevant_faqs[0]["a"]
        _exact_cache[key] = answer
        logger.info("faq_served", source="semantic_match")
        return FAQResult(answer=answer, source="semantic_match")

    # ✅ Layer 3: AI generation — only for ambiguous or novel questions.
    #    Context is tightly bounded: only the relevant FAQs, not all 200.
    context = "\n".join(f"Q: {f['q']}\nA: {f['a']}" for f in relevant_faqs)
    prompt = f"Relevant FAQ entries:\n{context}\n\nCustomer question: {user_question}"

    # ✅ Use the smallest model capable of the task.
    #    FAQ answering is rephrasing, not reasoning. Mini is sufficient.
    response = client.chat.completions.create(
        model="gpt-4o-mini",             # ✅ ~20x cheaper than gpt-4o
        messages=[
            {"role": "system", "content": "Answer the customer question using only the FAQ context provided."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=200,                  # ✅ Bounded — FAQ answers don't need 4096 tokens
        temperature=0.1,
    )

    answer = response.choices[0].message.content
    _exact_cache[key] = answer

    # ✅ Log token usage for cost tracking and anomaly detection.
    logger.info(
        "faq_served",
        source="ai_generated",
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens,
    )

    return FAQResult(
        answer=answer,
        source="ai_generated",
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens,
    )


def _is_high_confidence_match(faq: dict, query_emb: np.ndarray) -> bool:
    """Return True when the FAQ embedding is very close to the query embedding.

    Cosine similarity > 0.92 means the phrasing is near-identical — the stored
    answer can be returned directly without spending tokens on an AI call.
    ``faq["emb"]`` is the precomputed embedding attached by ``_semantic_search``.
    """
    faq_emb: np.ndarray = faq["emb"]
    norm = np.linalg.norm(faq_emb) * np.linalg.norm(query_emb)
    if norm == 0:
        return False
    return float(np.dot(faq_emb, query_emb) / norm) > 0.92


def _is_standalone_query(query: str) -> bool:
    """Heuristic: does this query make sense without any prior conversation?

    Queries containing anaphoric tokens ('it', 'that order', 'they', …) implicitly
    reference a previous turn and cannot be answered from a stateless FAQ cache.
    CONTEXT_SENSITIVE_SIGNALS holds the full list of such tokens.
    """
    tokens = set(query.strip().lower().split())
    return not tokens.intersection(CONTEXT_SENSITIVE_SIGNALS)


def _is_policy_stable_answer(answer: str) -> bool:
    """Return True when the answer covers a policy topic that rarely changes.

    Stable answers (shipping times, return policy, warranty…) are good candidates
    for a longer cache TTL — e.g. 24 h instead of 1 h — to reduce unnecessary
    re-generation after a cache miss.
    """
    return bool(_STABLE_POLICY_RE.search(answer))


# ✅ Cost calculation for 10,000 questions/day:
#
# Assumptions: 60% exact cache hits, 30% semantic match, 10% AI generation
#
# Exact cache (6,000 calls):    $0
# Semantic match (3,000 calls): embedding only, ~$0.02 total
# AI generation (1,000 calls):  ~300 input tokens × $0.15/1M = ~$0.05
#                                200 output tokens × $0.60/1M = ~$0.12
#
# Daily total:                  ~$0.19
# Monthly:                      ~$5.70
#
# vs the violation: ~$61,000/month
# Savings: 99.99%

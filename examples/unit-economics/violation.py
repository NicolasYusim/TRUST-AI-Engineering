# Unit Economics — Violation
# Scenario: FAQ chatbot for an e-commerce platform

import openai

client = openai.OpenAI()

# ❌ All documents are loaded and dumped into every single request.
#    This FAQ has 200 entries. That's ~40,000 tokens of context per call.
FAQ_DATABASE = [
    {"q": "What is your return policy?", "a": "30 days, no questions asked."},
    {"q": "How long does shipping take?", "a": "3-5 business days."},
    # ... 198 more entries
]


def answer_faq(user_question: str) -> str:
    # ❌ All FAQs are injected into every prompt regardless of relevance.
    #    A question about shipping injects the entire database including
    #    unrelated entries about returns, payments, accounts, etc.
    all_faqs = "\n".join(
        f"Q: {item['q']}\nA: {item['a']}" for item in FAQ_DATABASE
    )

    prompt = f"""You are a helpful customer support agent.
Here is our complete FAQ database:

{all_faqs}

Answer this customer question: {user_question}"""

    # ❌ Using GPT-4o for a task that is essentially lookup + rephrase.
    #    This task does not require frontier-level reasoning.
    #    GPT-4o costs ~20x more than GPT-4o-mini for similar FAQ quality.
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        # ❌ max_tokens not set — defaults to model maximum (4096)
        #    A FAQ answer needs ~100 tokens. We're paying for 4096.
    )

    return response.choices[0].message.content


# ❌ Cost calculation for 10,000 questions/day:
#
# Input tokens per call:  ~40,000 (all FAQs) + ~50 (question) = ~40,050
# Output tokens per call: up to 4,096 (unbounded)
# GPT-4o pricing:         $5 / 1M input, $15 / 1M output
#
# Daily cost (input):     10,000 × 40,050 / 1,000,000 × $5 = $2,002
# Daily cost (output):    10,000 × 200 / 1,000,000 × $15 = $30 (conservative)
# Daily total:            ~$2,032
# Monthly:                ~$61,000
#
# A cacheable, routed implementation of the same feature: ~$200/month.

# Traceability — Violation
# Scenario: AI-powered document summarizer endpoint

import openai
import logging

logger = logging.getLogger(__name__)
client = openai.OpenAI()


def summarize_document(document_text: str) -> str:
    """
    Summarizes a document using GPT.
    """

    # ❌ Prompt is built inline — never versioned, never stored anywhere.
    #    If the prompt changes, there's no history of what it was before.
    prompt = f"""
    Please summarize the following document in 3 bullet points.
    Be concise and focus on the key takeaways.

    Document:
    {document_text}
    """

    # ❌ Model is pinned to an alias, not a specific version.
    #    "gpt-4" could silently change behavior after an OpenAI update.
    #    In 6 months you won't know which version was running in production.
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
    )

    result = response.choices[0].message.content

    # ❌ Logging the result as a raw string with no structure.
    #    - No request ID → can't correlate with user complaints
    #    - No model version → can't know what was running
    #    - No prompt version → can't reproduce the call
    #    - No token counts → can't compute cost or debug performance
    logger.info(f"Summary generated: {result[:100]}...")

    return result


# ❌ What happens when a user reports "the summary was wrong"?
#
# You cannot answer:
# - Which model version answered?
# - What exact prompt was used?
# - What did the retrieved chunks look like?
# - Was this a one-off or a pattern?
#
# You are debugging blind.

# Traceability — Correct Implementation
# Scenario: AI-powered document summarizer endpoint

import uuid
import openai
import structlog
from pathlib import Path

logger = structlog.get_logger()
client = openai.OpenAI()

# ✅ Prompt is stored as a versioned file in the repository.
#    Changing the prompt = changing a file = a Git commit with a diff and blame.
#    Version string is embedded in the filename for easy reference.
PROMPT_VERSION = "summarize_v2.1.0"
PROMPT_TEMPLATE = Path(f"prompts/{PROMPT_VERSION}.txt").read_text()

# ✅ Model is pinned to an exact snapshot, not an alias.
#    This version will not change behavior after provider updates.
#    You can find the changelog for this exact version in OpenAI's release notes.
MODEL_VERSION = "gpt-4o-2024-08-06"


def summarize_document(document_text: str) -> dict:
    """
    Summarizes a document using GPT.
    Returns a dict with the result AND its full provenance.
    """

    # ✅ Every call gets a unique ID.
    #    This ID travels through logs, is returned to the caller,
    #    and can be stored in the DB alongside the result.
    request_id = str(uuid.uuid4())

    prompt = PROMPT_TEMPLATE.format(document=document_text)

    # ✅ Log the full call context BEFORE the call.
    #    If the call hangs or crashes, we still have the inputs in the log.
    logger.info(
        "ai_call_start",
        request_id=request_id,
        model=MODEL_VERSION,
        prompt_version=PROMPT_VERSION,
        input_length=len(document_text),
    )

    response = client.chat.completions.create(
        model=MODEL_VERSION,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=512,
        temperature=0.2,
    )

    result = response.choices[0].message.content

    # ✅ Log the full call context AFTER the call, with output metrics.
    #    Every field here is recoverable from logs for any past request.
    logger.info(
        "ai_call_complete",
        request_id=request_id,
        model=MODEL_VERSION,
        prompt_version=PROMPT_VERSION,
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens,
        finish_reason=response.choices[0].finish_reason,
    )

    # ✅ Return provenance alongside the result.
    #    The caller can store this in the database, show it in debug UI,
    #    or use it to reconstruct the call later.
    return {
        "summary": result,
        "provenance": {
            "request_id": request_id,
            "model": MODEL_VERSION,
            "prompt_version": PROMPT_VERSION,
        },
    }


# ✅ What happens when a user reports "the summary was wrong"?
#
# You can answer all of these:
# - request_id → find the exact log entry
# - model → gpt-4o-2024-08-06, unchanged since deploy
# - prompt → git show HEAD:prompts/summarize_v2.1.0.txt
# - tokens → 847 input, 203 output
# - You can replay the exact call with the exact inputs.

"""Executable reference: privacy-aware traceability for document summarization.

Guarantees:
- immutable references connect input, instruction, output, model, and run;
- an authorized caller can reconstruct the observable call;
- the example runs offline with a deterministic fake client.

Does not guarantee:
- that the summary is true or useful;
- that a real probabilistic/retired provider reproduces identical bytes;
- that this in-memory artifact store is suitable for sensitive production data.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Protocol


INSTRUCTION_ID = "summarize:v3.0.0"
INSTRUCTION = "Summarize the supplied document in one concise sentence."
MODEL_ID = "fake-summarizer:v1"


class SummarizerClient(Protocol):
    model_id: str

    def complete(self, instruction: str, document: str) -> tuple[str, str]:
        """Return (provider_request_id, summary)."""


@dataclass
class ArtifactStore:
    """Reference store used by the example.

    Production adapters need encryption, access control, retention, and deletion.
    """

    artifacts: dict[str, str] = field(default_factory=dict)

    def put(self, kind: str, content: str) -> str:
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        reference = f"{kind}:sha256:{digest}"
        self.artifacts[reference] = content
        return reference

    def get(self, reference: str) -> str:
        return self.artifacts[reference]


@dataclass
class TraceStore:
    traces: dict[str, dict] = field(default_factory=dict)

    def append(self, trace: dict) -> None:
        run_id = trace["run_id"]
        if run_id in self.traces:
            raise ValueError(f"trace already exists: {run_id}")
        self.traces[run_id] = trace


class FakeSummarizer:
    model_id = MODEL_ID

    def complete(self, instruction: str, document: str) -> tuple[str, str]:
        words = document.strip().split()
        summary = " ".join(words[:12])
        if len(words) > 12:
            summary += "…"
        request_id = hashlib.sha256(
            f"{instruction}\0{document}".encode("utf-8")
        ).hexdigest()[:16]
        return f"fake-{request_id}", summary


def summarize_document(
    document_text: str,
    *,
    client: SummarizerClient,
    artifacts: ArtifactStore,
    traces: TraceStore,
) -> dict:
    if not document_text.strip():
        raise ValueError("document must not be empty")

    run_id = str(uuid.uuid4())
    input_ref = artifacts.put("input", document_text)
    instruction_ref = artifacts.put("instruction", INSTRUCTION)

    provider_request_id, summary = client.complete(INSTRUCTION, document_text)
    output_ref = artifacts.put("output", summary)

    trace = {
        "run_id": run_id,
        "component": "document-summarizer",
        "instruction_id": INSTRUCTION_ID,
        "instruction_artifact": instruction_ref,
        "model_id": client.model_id,
        "input_artifact": input_ref,
        "source_artifacts": [input_ref],
        "provider_request_id": provider_request_id,
        "output_artifact": output_ref,
        "status": "completed",
    }
    traces.append(trace)
    return {"summary": summary, "trace": trace}


def replay_observable_call(
    trace: dict,
    *,
    client: SummarizerClient,
    artifacts: ArtifactStore,
) -> str:
    """Replay captured observable inputs.

    Equality is expected from FakeSummarizer, not promised for real providers.
    """

    instruction = artifacts.get(trace["instruction_artifact"])
    document = artifacts.get(trace["input_artifact"])
    _, summary = client.complete(instruction, document)
    return summary

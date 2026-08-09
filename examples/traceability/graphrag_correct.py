"""Executable reference: GraphRAG traversal provenance.

Guarantees complete recording of the deterministic fixture traversal. It does not
prove that the graph facts are current or that the generated answer is correct.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


GRAPH_VERSION = "corporate-graph:v1"
ALLOWED_RELATIONSHIPS = {"SUBSIDIARY_OF", "OPERATES_IN"}


@dataclass(frozen=True)
class Edge:
    source: str
    relationship: str
    target: str


GRAPH = (
    Edge("greenpower", "SUBSIDIARY_OF", "acme"),
    Edge("greenpower", "OPERATES_IN", "renewable-energy"),
    Edge("logistics", "SUBSIDIARY_OF", "acme"),
    Edge("logistics", "OPERATES_IN", "freight"),
)


class FakeAnswerClient:
    model_id = "fake-graph-answerer:v1"

    def complete(self, question: str, facts: list[Edge]) -> str:
        renewable = sorted(
            edge.source
            for edge in facts
            if edge.relationship == "OPERATES_IN"
            and edge.target == "renewable-energy"
        )
        return ", ".join(renewable) if renewable else "No supported answer"


def answer_graph_query(question: str, client: FakeAnswerClient | None = None) -> dict:
    client = client or FakeAnswerClient()
    run_id = str(uuid.uuid4())

    seed = {"text": "Acme", "node_id": "acme", "resolution": "exact_fixture_match"}
    subsidiary_edges = [
        edge
        for edge in GRAPH
        if edge.relationship == "SUBSIDIARY_OF" and edge.target == seed["node_id"]
    ]
    subsidiary_ids = {edge.source for edge in subsidiary_edges}
    domain_edges = [
        edge
        for edge in GRAPH
        if edge.relationship == "OPERATES_IN" and edge.source in subsidiary_ids
    ]
    answer_source_ids = {
        edge.source
        for edge in domain_edges
        if edge.target == "renewable-energy"
    }
    context = subsidiary_edges + domain_edges

    for edge in context:
        if edge.relationship not in ALLOWED_RELATIONSHIPS:
            raise ValueError(f"relationship is not allowed: {edge.relationship}")

    hops = [
        {
            "index": index,
            "source": edge.source,
            "relationship": edge.relationship,
            "target": edge.target,
        }
        for index, edge in enumerate(context)
    ]
    answer = client.complete(question, context)
    trace = {
        "run_id": run_id,
        "component": "graphrag-answerer",
        "graph_version": GRAPH_VERSION,
        "model_id": client.model_id,
        "seed_entities": [seed],
        "hops": hops,
        "context_node_ids": sorted(
            {node for edge in context for node in (edge.source, edge.target)}
        ),
        "answer_source_node_ids": sorted(answer_source_ids),
    }
    return {"answer": answer, "trace": trace}

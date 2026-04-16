# GraphRAG Traceability — Correct Implementation
# Scenario: Knowledge graph query answering over a corporate knowledge graph
#
# User query: "Which subsidiaries of Acme Corp operate in renewable energy
#              and have partnerships with European firms?"

import uuid
import openai
import structlog
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional

logger = structlog.get_logger()
client = openai.OpenAI()

ENTITY_EXTRACT_PROMPT_VERSION = "graphrag_entity_extract_v1.2.0"
ANSWER_PROMPT_VERSION = "graphrag_answer_v1.0.0"
MODEL_VERSION = "gpt-4o-2024-08-06"

MAX_HOP_DEPTH = 3


# ─── PYDANTIC MODELS ──────────────────────────────────────────────────────────

class SeedEntity(BaseModel):
    """An entity extracted from the user query and resolved to a graph node."""
    text: str                              # raw mention as it appears in the query
    node_id: str                           # resolved node ID in the knowledge graph
    node_label: str                        # ontology type, e.g. "Company", "Person"
    confidence: float = Field(ge=0.0, le=1.0)
    disambiguation_note: Optional[str] = None  # set when multiple nodes matched


class SeedExtractionResult(BaseModel):
    """Structured output from the entity-extraction LLM call."""
    entities: list[SeedEntity]


class GraphHop(BaseModel):
    """A single edge traversal from one graph node to another."""
    hop_index: int                # 0-based depth level in the traversal tree
    source_node_id: str
    source_node_label: str
    relationship_type: str        # edge label, e.g. "SUBSIDIARY_OF", "OPERATES_IN"
    target_node_id: str
    target_node_label: str
    hop_score: Optional[float] = None  # relevance/salience score if available


class TraversalContext(BaseModel):
    """The final subgraph serialized into the generation prompt."""
    included_node_ids: list[str]
    included_relationship_types: list[str]
    total_nodes: int
    total_edges: int


# ─── GRAPH STUB ───────────────────────────────────────────────────────────────

def _graph_neighbors(
    node_id: str,
    relationship_type: str,
) -> list[dict]:
    """
    Stub: replace with your actual graph DB call (Neo4j, Neptune, etc.).
    Returns a list of {id, label, type, score} dicts.
    """
    GRAPH: dict[str, list[dict]] = {
        "company:acme_corp": [
            {"id": "company:greenpower_gmbh", "label": "GreenPower GmbH",
             "type": "Company", "score": 0.91},
            {"id": "company:solarfield_bv",   "label": "SolarField BV",
             "type": "Company", "score": 0.87},
            {"id": "company:acme_logistics",  "label": "Acme Logistics Ltd",
             "type": "Company", "score": 0.55},
        ],
        "company:greenpower_gmbh": [
            {"id": "company:nordic_wind_as",  "label": "Nordic Wind AS",
             "type": "Company", "score": 0.88},
        ],
        "company:solarfield_bv": [
            {"id": "company:iberian_solar_sa", "label": "Iberian Solar SA",
             "type": "Company", "score": 0.82},
        ],
    }
    return GRAPH.get(node_id, [])


def _resolve_node_id(text: str) -> tuple[str, str, float, Optional[str]]:
    """
    Stub: resolve a raw entity mention to (node_id, node_label, confidence,
    disambiguation_note). Replace with your graph's entity linker.
    """
    INDEX = {
        "Acme Corp": ("company:acme_corp",    "Company", 0.97, None),
        "renewable energy": (
            "sector:renewable_energy", "Sector", 0.89,
            "Matched canonical sector node; 'clean energy' alias also considered.",
        ),
        "European": ("region:europe", "Region", 0.76, None),
    }
    return INDEX.get(text, (f"unknown:{text.lower().replace(' ', '_')}",
                            "Unknown", 0.40, f"No match found for '{text}'."))


# ─── SEED ENTITY EXTRACTION ───────────────────────────────────────────────────

def _extract_seed_entities(
    user_query: str,
    traversal_id: str,
) -> list[SeedEntity]:
    """
    Use an LLM with structured output to extract and resolve seed entities.
    Every extraction decision is logged before graph traversal begins.
    """
    # ✅ Structured output via Pydantic — the response is validated at parse
    #    time. A malformed extraction fails loudly instead of silently
    #    injecting garbage node IDs into the traversal.
    response = client.beta.chat.completions.parse(
        model=MODEL_VERSION,
        messages=[
            {
                "role": "system",
                "content": (
                    "Extract the named entities from the user query that should "
                    "serve as starting nodes for a knowledge graph traversal. "
                    "Return each entity with its canonical text as it appears in "
                    "the query. Do not invent entities not present in the query."
                ),
            },
            {"role": "user", "content": user_query},
        ],
        response_format=SeedExtractionResult,
        max_tokens=256,
        temperature=0.0,
    )
    raw_entities = response.parsed.entities

    # ✅ Resolve each extracted mention to a concrete graph node.
    #    Disambiguation notes are recorded so that any resolution ambiguity
    #    is visible in the log — not silently applied.
    resolved: list[SeedEntity] = []
    for entity in raw_entities:
        node_id, node_label, confidence, note = _resolve_node_id(entity.text)
        seed = SeedEntity(
            text=entity.text,
            node_id=node_id,
            node_label=node_label,
            confidence=confidence,
            disambiguation_note=note,
        )
        resolved.append(seed)

        # ✅ One structured log entry per seed entity.
        #    If a wrong node is resolved, this entry is the first place to look.
        logger.info(
            "graphrag_seed_entity_resolved",
            traversal_id=traversal_id,
            entity_text=seed.text,
            node_id=seed.node_id,
            node_label=seed.node_label,
            confidence=seed.confidence,
            disambiguation_note=seed.disambiguation_note,
            prompt_version=ENTITY_EXTRACT_PROMPT_VERSION,
        )

    return resolved


# ─── GRAPH TRAVERSAL ─────────────────────────────────────────────────────────

def _traverse(
    seed_entities: list[SeedEntity],
    relationship_type: str,
    max_depth: int,
    traversal_id: str,
) -> tuple[list[GraphHop], set[str]]:
    """
    BFS over the knowledge graph up to max_depth hops.
    Every hop is logged as a discrete, numbered event.
    """
    hops: list[GraphHop] = []
    visited_node_ids: set[str] = {e.node_id for e in seed_entities}
    frontier = [(e.node_id, e.node_label, 0) for e in seed_entities]

    while frontier:
        source_id, source_label, depth = frontier.pop(0)
        if depth >= max_depth:
            continue

        neighbors = _graph_neighbors(source_id, relationship_type)
        for neighbor in neighbors:
            hop = GraphHop(
                hop_index=depth,
                source_node_id=source_id,
                source_node_label=source_label,
                relationship_type=relationship_type,
                target_node_id=neighbor["id"],
                target_node_label=neighbor["label"],
                hop_score=neighbor.get("score"),
            )
            hops.append(hop)

            # ✅ Every hop is logged individually, including depth and score.
            #    This makes it possible to answer post-hoc:
            #    "Why did the context include Nordic Wind AS?" →
            #    hop_index=1, source=GreenPower GmbH, score=0.88.
            logger.info(
                "graphrag_hop",
                traversal_id=traversal_id,
                hop_index=hop.hop_index,
                source_node_id=hop.source_node_id,
                source_node_label=hop.source_node_label,
                relationship_type=hop.relationship_type,
                target_node_id=hop.target_node_id,
                target_node_label=hop.target_node_label,
                hop_score=hop.hop_score,
            )

            if neighbor["id"] not in visited_node_ids:
                visited_node_ids.add(neighbor["id"])
                frontier.append((neighbor["id"], neighbor["label"], depth + 1))

    return hops, visited_node_ids


# ─── CONTEXT ASSEMBLY & GENERATION ──────────────────────────────────────────

def answer_graph_query(user_query: str) -> dict:
    """
    Full GraphRAG pipeline: extract → traverse → assemble context → generate.
    Returns the answer alongside its full traversal provenance.
    """

    # ✅ A single ID ties every log event for this request together —
    #    seed extraction, all hops, context assembly, and the final answer.
    traversal_id = str(uuid.uuid4())

    logger.info(
        "graphrag_query_start",
        traversal_id=traversal_id,
        query=user_query,
    )

    # Step 1 — extract and resolve seed entities
    seed_entities = _extract_seed_entities(user_query, traversal_id)

    # Step 2 — traverse the graph
    # ✅ Relationship type is an explicit parameter, not a magic string buried
    #    in a helper function. The log captures exactly which edge type was used,
    #    making it easy to correlate over-broad traversals with bad answers.
    hops, visited_node_ids = _traverse(
        seed_entities=seed_entities,
        relationship_type="SUBSIDIARY_OF",
        max_depth=MAX_HOP_DEPTH,
        traversal_id=traversal_id,
    )

    # ✅ Log the subgraph boundary: every node and edge type that entered context.
    #    This is the "shape" of the context window from a graph perspective.
    ctx = TraversalContext(
        included_node_ids=sorted(visited_node_ids),
        included_relationship_types=list({h.relationship_type for h in hops}),
        total_nodes=len(visited_node_ids),
        total_edges=len(hops),
    )
    logger.info(
        "graphrag_context_assembled",
        traversal_id=traversal_id,
        **ctx.model_dump(),
    )

    # Step 3 — serialize the subgraph into a generation prompt
    context_lines = [
        f"- {h.source_node_label} '{h.source_node_id}' "
        f"--[{h.relationship_type}]--> "
        f"{h.target_node_label} '{h.target_node_id}'"
        + (f"  (score={h.hop_score:.2f})" if h.hop_score is not None else "")
        for h in hops
    ]
    context_text = "\n".join(context_lines)

    # ✅ Prompt version is pinned and logged — changing the answer format
    #    requires a version bump, which creates a diff and a Git commit.
    prompt = (
        f"Using only the knowledge graph facts below, answer the question.\n"
        f"For each company you mention, cite its node ID.\n\n"
        f"Question: {user_query}\n\n"
        f"Graph facts:\n{context_text}"
    )

    response = client.chat.completions.create(
        model=MODEL_VERSION,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=512,
        temperature=0.1,
    )
    answer = response.choices[0].message.content

    # ✅ Final log entry closes the traversal trace with token usage.
    #    Every field is recoverable for any past request.
    logger.info(
        "graphrag_query_complete",
        traversal_id=traversal_id,
        model=MODEL_VERSION,
        answer_prompt_version=ANSWER_PROMPT_VERSION,
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens,
        finish_reason=response.choices[0].finish_reason,
        total_hops=len(hops),
        total_context_nodes=ctx.total_nodes,
    )

    # ✅ Provenance is returned alongside the answer so the caller can
    #    store it in the database, surface it in a debug UI, or feed it
    #    into a groundedness evaluation pipeline.
    return {
        "answer": answer,
        "provenance": {
            "traversal_id": traversal_id,
            "model": MODEL_VERSION,
            "entity_extract_prompt_version": ENTITY_EXTRACT_PROMPT_VERSION,
            "answer_prompt_version": ANSWER_PROMPT_VERSION,
            "seed_entities": [e.model_dump() for e in seed_entities],
            "hops": [h.model_dump() for h in hops],
            "context": ctx.model_dump(),
        },
    }

# GraphRAG Traceability — Violation
# Scenario: Knowledge graph query answering over a corporate knowledge graph
#
# User query: "Which subsidiaries of Acme Corp operate in renewable energy
#              and have partnerships with European firms?"

import logging
import openai

logger = logging.getLogger(__name__)
client = openai.OpenAI()


def _fake_graph_query(entity: str, rel_type: str) -> list[dict]:
    """Stub: pretends to query a knowledge graph."""
    return [
        {"id": "node_42", "label": "GreenPower GmbH", "type": "Company"},
        {"id": "node_77", "label": "SolarEdge BV",    "type": "Company"},
    ]


def answer_graph_query(user_query: str) -> str:
    # ❌ Seed entities extracted by a naive string split — no model, no
    #    confidence scores, no disambiguation, no node resolution.
    #    "Acme Corp" could match a dozen nodes in the graph; we pick none.
    words = user_query.split()
    seed_entities = [w for w in words if w[0].isupper()]

    # ❌ No log of what was extracted, no IDs, no confidence values.
    #    If the wrong entity is resolved, there is no record.
    logger.info(f"Extracted entities: {seed_entities}")

    all_nodes: list[dict] = []
    for entity in seed_entities:
        # ❌ Relationship type is hard-coded as a magic string — if the graph
        #    schema changes, the query silently returns empty results.
        nodes = _fake_graph_query(entity, "RELATED_TO")
        all_nodes.extend(nodes)

        # ❌ No hop-level logging: we do not record which source node triggered
        #    this traversal, what relationship was used, or what score the hop
        #    received. Debugging a wrong answer is impossible.

    # ❌ Second-hop traversal happens invisibly — no log of depth, no record
    #    of which nodes triggered the deeper search.
    second_hop_nodes: list[dict] = []
    for node in all_nodes:
        deeper = _fake_graph_query(node["id"], "RELATED_TO")
        second_hop_nodes.extend(deeper)

    context_nodes = all_nodes + second_hop_nodes

    # ❌ Context assembly is invisible: we cannot tell which nodes ended up in
    #    the prompt, in what order, or how many tokens they consumed.
    context_text = "\n".join(n["label"] for n in context_nodes)

    prompt = f"""
    Answer the following question using the context below.

    Question: {user_query}

    Context:
    {context_text}
    """

    response = client.chat.completions.create(
        # ❌ Model alias — behavior can change after a provider update.
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
    )

    answer = response.choices[0].message.content

    # ❌ Final log contains only the answer snippet — no traversal ID,
    #    no list of traversed nodes, no hop count, no model version.
    logger.info(f"Graph query answered: {answer[:80]}...")

    return answer


# ❌ When a user reports "the answer mentioned a company we divested three
#    years ago", you cannot investigate:
#
#  - Which seed entity resolved to the wrong starting node?
#  - Which hop introduced the stale node into context?
#  - Was the "RELATED_TO" edge too broad and pulled in unrelated subgraphs?
#  - How many nodes were in the context — did truncation hide relevant data?
#
#  Every traversal step is a black box.

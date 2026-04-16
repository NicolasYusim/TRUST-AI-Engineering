# Agentic Sandboxing — Violation
# Scenario: Automated support-ticket processor (classify → enrich → route)
#
# Anti-patterns demonstrated:
#   ❌  All tools available at every stage — no per-node filtering
#   ❌  No effect budget — model issues unlimited side-effecting calls
#   ❌  No step limit — inner loop runs until context window fills
#   ❌  No output schema — routing decision buried in free-form text
#   ❌  Transition not validated — code advances blindly between nodes

from __future__ import annotations

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from typing import TypedDict, Annotated

llm = ChatOpenAI(model="gpt-4o", temperature=0)


# ── Tools — read-only and write, all in one flat list ─────────────────────────

@tool
def search_kb(query: str) -> str:
    """Search the knowledge base. Read-only."""
    return f"[KB results for: {query}]"


@tool
def list_categories() -> list[str]:
    """Return valid ticket categories. Read-only."""
    return ["billing", "technical", "account", "shipping"]


@tool
def get_customer_profile(customer_id: str) -> dict:
    """Fetch customer profile. Read-only."""
    return {"id": customer_id, "tier": "gold", "open_tickets": 3}


@tool
def lookup_order(order_id: str) -> dict:
    """Look up order status. Read-only."""
    return {"order_id": order_id, "status": "shipped"}


@tool
def assign_to_queue(queue: str, ticket_id: str, priority: int) -> str:
    """Assign ticket to support queue. WRITE: updates routing database."""
    print(f"[DB WRITE] {ticket_id} → {queue}  priority={priority}")
    return f"Ticket assigned to {queue}"


@tool
def send_notification(channel: str, recipient: str, body: str) -> str:
    """Send customer/agent notification. WRITE: sends email or SMS."""
    print(f"[EMAIL SENT] {channel} → {recipient}: {body[:60]}")
    return f"Notification sent via {channel}"


@tool
def override_priority(ticket_id: str, new_priority: int) -> str:
    """Admin: force-set ticket priority. WRITE: admin system mutation."""
    print(f"[ADMIN WRITE] {ticket_id} → priority {new_priority}")
    return "Priority overridden"


@tool
def archive_as_duplicate(ticket_id: str, canonical_id: str) -> str:
    """Admin: archive ticket as duplicate. WRITE: irreversible."""
    print(f"[ADMIN WRITE] Archived {ticket_id} as duplicate of {canonical_id}")
    return "Ticket archived"


# ❌ Every tool — including admin writes — is in a single global pool.
#    Every node gets the same unrestricted set.
ALL_TOOLS = [
    search_kb, list_categories, get_customer_profile, lookup_order,
    assign_to_queue, send_notification, override_priority, archive_as_duplicate,
]
_TOOL_MAP = {t.name: t for t in ALL_TOOLS}
llm_with_tools = llm.bind_tools(ALL_TOOLS)


# ── State ──────────────────────────────────────────────────────────────────────

class TicketState(TypedDict):
    ticket_id:   str
    ticket_text: str
    messages:    Annotated[list, add_messages]
    # ❌ No effect counter. No per-node contract. No validated result fields.


# ── Shared agent loop — used by all three nodes ───────────────────────────────

def _run_agent_loop(messages: list) -> list:
    """
    Standard ReAct loop: call LLM, execute tool calls, repeat.
    ❌ No step limit:    loops until context window fills or API times out.
    ❌ No effect budget: send_notification can fire 10 times — code won't notice.
    ❌ No tool filter:   every tool in ALL_TOOLS is available at every stage.
    """
    while True:
        response: AIMessage = llm_with_tools.invoke(messages)
        messages = messages + [response]

        if not response.tool_calls:
            break   # ❌ model decides when it's done — no external constraint

        for tc in response.tool_calls:
            # ❌ No check: is this tool permitted at this node?
            # ❌ No check: is this an effect tool and has the budget been exceeded?
            result = _TOOL_MAP[tc["name"]].invoke(tc["args"])
            messages = messages + [ToolMessage(content=str(result), tool_call_id=tc["id"])]

    return messages


# ── Nodes ──────────────────────────────────────────────────────────────────────

def classify_node(state: TicketState) -> dict:
    # ❌ classify_node sees assign_to_queue, override_priority, archive_as_duplicate.
    #    The model can fire an admin write before classification is even complete.
    messages = _run_agent_loop(state["messages"])
    return {"messages": messages[len(state["messages"]):]}


def enrich_node(state: TicketState) -> dict:
    # ❌ No assertion that classify_node produced a valid decision before
    #    we proceed. Messages may contain incomplete or ambiguous output.
    messages = _run_agent_loop(state["messages"])
    return {"messages": messages[len(state["messages"]):]}


def route_node(state: TicketState) -> dict:
    # ❌ No effect budget. The model can call send_notification and
    #    assign_to_queue an unlimited number of times in one invocation.
    messages = _run_agent_loop(state["messages"])
    return {"messages": messages[len(state["messages"]):]}


# ── Graph ──────────────────────────────────────────────────────────────────────

builder = StateGraph(TicketState)
builder.add_node("classify", classify_node)
builder.add_node("enrich",   enrich_node)
builder.add_node("route",    route_node)
builder.set_entry_point("classify")

# ❌ Code advances unconditionally between nodes — no validation that the
#    previous node produced a complete, well-formed decision before we proceed.
builder.add_edge("classify", "enrich")
builder.add_edge("enrich",   "route")
builder.add_edge("route",    END)

app = builder.compile()


# ── Bugs that appear in production ────────────────────────────────────────────
#
# BUG 1 — EFFECT STORM (send_notification × N)
#   route_node has no effect budget. The model calls send_notification for the
#   customer, the assigned agent, and the team lead. Customer receives 3 emails
#   before any agent opens the ticket. Support sees duplicate assignments.
#
# BUG 2 — WRITE TOOL LEAKAGE (admin action in wrong stage)
#   classify_node calls override_priority("T-1042", 1) because the ticket text
#   contains the word "urgent". The admin write fires before enrichment has
#   verified the customer's actual tier. No contract prevented it.
#
# BUG 3 — IRREVERSIBLE DELETE
#   The model calls archive_as_duplicate("T-1042", "T-0923") because a KB
#   search returned a vaguely similar article. T-1042 is permanently gone.
#   No human approved this. archive_as_duplicate was never intended to be
#   available at classification time — there was just no contract to say so.
#
# BUG 4 — INFINITE LOOP
#   The model alternates between search_kb and list_categories calls, never
#   satisfied with its confidence threshold. No MAX_TOOL_ROUNDS guard exists.
#   The loop runs for 87 iterations, exhausting the 128K context window:
#   $2.40 per ticket instead of $0.03 expected.
#
# BUG 5 — BLIND TRANSITION
#   classify_node finishes with an ambiguous free-text conclusion.
#   Code unconditionally advances to enrich_node. enrich_node attempts to
#   extract a customer_id from messages and silently receives None.

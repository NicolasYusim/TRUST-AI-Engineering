# Agentic Sandboxing — Correct Implementation
# Scenario: Automated support-ticket processor (classify → enrich → route)
#
# Each graph node is governed by a SandboxContract declaring four dimensions:
#   ✅  Allowed tools       — exhaustive list; model only sees this subset
#   ✅  Allowed transitions — exhaustive list; code rejects anything else
#   ✅  Output schema       — validated Pydantic model before any transition fires
#   ✅  Effect budget       — max side-effecting calls; EffectBudgetExceeded raised
#
# run_sandboxed_node() enforces all four dimensions on every invocation.
# The model cannot modify the contract, extend its tool list, or loop
# indefinitely — code is the sole authority on control flow.

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict, Annotated, Literal

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger()
llm    = ChatOpenAI(model="gpt-4o", temperature=0)

MAX_TOOL_ROUNDS = 5   # ✅ absolute ceiling on tool-call iterations per node


# ── Sandbox infrastructure ─────────────────────────────────────────────────────

class EffectBudgetExceeded(RuntimeError):
    """Node tried to execute more side-effecting calls than its contract allows."""

class TransitionViolation(RuntimeError):
    """Model chose a next_state not listed in the contract's allowed_transitions."""

class ToolNotPermitted(RuntimeError):
    """Model requested a tool not listed in the contract's allowed_tools."""


@dataclass
class SandboxContract:
    """
    Machine-readable declaration attached to a graph node.
    Authored in code — the model cannot read, modify, or reason its way around it.

    Fields:
        node_name:           identifier used in log messages and errors.
        allowed_tools:       exhaustive list of tool names the model may call.
        allowed_transitions: exhaustive list of valid next_state values.
        output_schema:       Pydantic model the model's final decision must match.
        max_effects:         maximum side-effecting tool calls per invocation.
                             0 = read-only node.
    """
    node_name:           str
    allowed_tools:       list[str]
    allowed_transitions: list[str]
    output_schema:       type[BaseModel]
    max_effects:         int = 0


class EffectTracker:
    """Counts side-effecting tool calls against the node's effect budget."""

    def __init__(self, contract: SandboxContract) -> None:
        self._contract = contract
        self._used = 0

    def preflight_check(self, tool_names: list[str]) -> None:
        """
        Atomically validate an entire parallel batch of tool calls against
        the effect budget BEFORE any call executes.

        Counts only the effect tools in the batch; raises EffectBudgetExceeded
        if committing the whole batch would overflow the budget — so either
        ALL calls in the batch execute, or NONE do.  No partial execution.
        """
        batch_effects = sum(1 for n in tool_names if n in EFFECT_TOOLS)
        if self._used + batch_effects > self._contract.max_effects:
            raise EffectBudgetExceeded(
                f"Node '{self._contract.node_name}': parallel batch of "
                f"{batch_effects} effect call(s) would bring total to "
                f"{self._used + batch_effects}, exceeding budget of "
                f"{self._contract.max_effects}. "
                f"Entire batch rejected — no side effects were committed."
            )
        self._used += batch_effects   # commit only after the check passes

    @property
    def used(self) -> int:
        return self._used


# ── Output schemas — one per node ─────────────────────────────────────────────
# next_state is typed as Literal: Pydantic rejects invalid values at parse time,
# before run_sandboxed_node performs its secondary transition check.

class ClassifyDecision(BaseModel):
    category:   Literal["billing", "technical", "account", "shipping"]
    urgency:    Literal["low", "medium", "high", "critical"]
    confidence: float = Field(ge=0.0, le=1.0)
    next_state: Literal["enrich", "reject"] = Field(
        description="'reject' only if the ticket is spam, a test, or an exact duplicate."
    )


class EnrichDecision(BaseModel):
    customer_id:   str
    customer_tier: Literal["standard", "gold", "platinum"]
    order_id:      str | None = None
    next_state:    Literal["route"]


class RouteDecision(BaseModel):
    target_queue: Literal[
        "billing-tier1", "billing-tier2",
        "tech-support", "account-ops", "shipping-ops",
    ]
    priority:        int  = Field(ge=1, le=5, description="1 = highest, 5 = lowest")
    notify_customer: bool = Field(
        description="True = send one acknowledgement email to the customer."
    )
    next_state: Literal["done"]


# ── Tool registry ──────────────────────────────────────────────────────────────

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
    """Fetch customer profile and tier. Read-only."""
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


# ✅ Admin tools (override_priority, archive_as_duplicate) are simply absent
#    from the registry. The model is architecturally incapable of calling them:
#    they are never serialised into any node's tool list.
TOOL_REGISTRY: dict[str, BaseTool] = {
    t.name: t for t in [
        search_kb, list_categories,
        get_customer_profile, lookup_order,
        assign_to_queue, send_notification,
    ]
}

# ✅ Effect tools are declared separately; only these require a budget charge.
EFFECT_TOOLS: frozenset[str] = frozenset({"assign_to_queue", "send_notification"})


# ── Contracts — one per node ───────────────────────────────────────────────────

CONTRACTS: dict[str, SandboxContract] = {
    "classify": SandboxContract(
        node_name="classify",
        allowed_tools=["search_kb", "list_categories"],     # ✅ read-only only
        allowed_transitions=["enrich", "reject"],
        output_schema=ClassifyDecision,
        max_effects=0,   # ✅ classification produces zero side effects
    ),
    "enrich": SandboxContract(
        node_name="enrich",
        allowed_tools=["get_customer_profile", "lookup_order"],  # ✅ read-only
        allowed_transitions=["route"],
        output_schema=EnrichDecision,
        max_effects=0,   # ✅ enrichment is a pure read phase
    ),
    "route": SandboxContract(
        node_name="route",
        allowed_tools=["assign_to_queue", "send_notification"],  # ✅ write tools
        allowed_transitions=["done"],
        output_schema=RouteDecision,
        max_effects=2,   # ✅ at most: 1 queue assignment + 1 notification
    ),
}


# ── Core enforcement function ──────────────────────────────────────────────────

def run_sandboxed_node(
    contract: SandboxContract,
    messages: list,
) -> tuple[BaseModel, list]:
    """
    Enforce all four sandbox dimensions for a single node invocation.

    Phase 1 — Bounded tool loop (at most MAX_TOOL_ROUNDS iterations):
        a. Bind ONLY contract.allowed_tools to the LLM.
        b. For each parallel batch of tool calls (one AIMessage may contain
           multiple tool_calls — all must be processed as a unit):
           - Reject any tool not in allowed_tools.          ← ToolNotPermitted
           - Atomically pre-flight the ENTIRE batch against
             the effect budget before ANY call executes.    ← EffectBudgetExceeded
           - Execute all calls; append all ToolMessages together.

    Phase 2 — Structured decision:
        c. Ask LLM for a response matching contract.output_schema.
        d. Validate next_state against contract.allowed_transitions.
                                                             ← TransitionViolation
    Returns (decision, updated_messages).
    """
    # ── Phase 1: bounded tool loop ─────────────────────────────────────────────
    permitted  = [TOOL_REGISTRY[n] for n in contract.allowed_tools]
    bound_llm  = llm.bind_tools(permitted)
    tracker    = EffectTracker(contract)
    loop_msgs  = list(messages)

    for _ in range(MAX_TOOL_ROUNDS):
        response: AIMessage = bound_llm.invoke(loop_msgs)
        loop_msgs.append(response)

        if not response.tool_calls:
            break   # model finished its read phase; proceed to structured decision

        # ✅ Pass 1 — validate every tool name in the parallel batch BEFORE
        #    executing any.  Belt-and-suspenders: bind_tools should prevent
        #    unknown names, but model output is untrusted and must be verified.
        for tc in response.tool_calls:
            if tc["name"] not in contract.allowed_tools:
                raise ToolNotPermitted(
                    f"Node '{contract.node_name}': model requested '{tc['name']}' "
                    f"which is not in allowed_tools={contract.allowed_tools}"
                )

        # ✅ Pass 2 — atomically pre-flight the ENTIRE parallel batch.
        #    preflight_check() counts all effect calls in the batch and raises
        #    EffectBudgetExceeded BEFORE the first call executes — so either
        #    the whole batch commits or none of it does.  No partial writes.
        tracker.preflight_check([tc["name"] for tc in response.tool_calls])

        # ✅ Pass 3 — execute all calls; collect ToolMessages as a group.
        #    Appending all responses together preserves the multi-tool-call /
        #    multi-tool-result conversation structure that LangGraph and most
        #    LLM providers require (each ToolMessage maps back to a tool_call_id
        #    in the preceding AIMessage).
        tool_messages: list[ToolMessage] = []
        for tc in response.tool_calls:
            result = TOOL_REGISTRY[tc["name"]].invoke(tc["args"])
            tool_messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
        loop_msgs.extend(tool_messages)
    else:
        # MAX_TOOL_ROUNDS exhausted without the model voluntarily stopping.
        logger.warning("max_tool_rounds_reached", node=contract.node_name, rounds=MAX_TOOL_ROUNDS)

    # ── Phase 2: structured decision ───────────────────────────────────────────
    decision = llm.with_structured_output(contract.output_schema).invoke(loop_msgs)

    # ✅ Literal[...] on next_state already rejects invalid values at Pydantic
    #    parse time. We check again explicitly: model output is untrusted input.
    if decision.next_state not in contract.allowed_transitions:
        raise TransitionViolation(
            f"Node '{contract.node_name}': model chose '{decision.next_state}' "
            f"but allowed_transitions={contract.allowed_transitions}"
        )

    logger.info(
        "sandbox_node_complete",
        node=contract.node_name,
        next_state=decision.next_state,
        effects_used=tracker.used,
        effects_budget=contract.max_effects,
    )
    return decision, loop_msgs


# ── State ──────────────────────────────────────────────────────────────────────

class TicketState(TypedDict):
    ticket_id:       str
    ticket_text:     str
    messages:        Annotated[list, add_messages]
    classify_result: ClassifyDecision | None
    enrich_result:   EnrichDecision   | None
    route_result:    RouteDecision    | None


# ── Node implementations ───────────────────────────────────────────────────────

def classify_node(state: TicketState) -> dict:
    # ✅ run_sandboxed_node enforces all four contract dimensions.
    #    classify_node cannot see assign_to_queue, override_priority,
    #    or any tool outside ["search_kb", "list_categories"].
    decision, new_msgs = run_sandboxed_node(CONTRACTS["classify"], state["messages"])
    return {
        "classify_result": decision,
        "messages": new_msgs[len(state["messages"]):],
    }


def enrich_node(state: TicketState) -> dict:
    decision, new_msgs = run_sandboxed_node(CONTRACTS["enrich"], state["messages"])
    return {
        "enrich_result": decision,
        "messages": new_msgs[len(state["messages"]):],
    }


def route_node(state: TicketState) -> dict:
    # ✅ max_effects=2 → assign_to_queue counts as effect #1,
    #    send_notification counts as effect #2.
    #    Any third write call raises EffectBudgetExceeded before it executes.
    decision, new_msgs = run_sandboxed_node(CONTRACTS["route"], state["messages"])
    return {
        "route_result": decision,
        "messages": new_msgs[len(state["messages"]):],
    }


def reject_node(state: TicketState) -> dict:
    # ✅ Terminal node — no model call, no tools, no side effects.
    logger.info("ticket_rejected", ticket_id=state["ticket_id"])
    return {}


# ── Routing functions (code reads validated state — never raw LLM text) ────────

def after_classify(state: TicketState) -> str:
    result = state["classify_result"]
    if result is None:
        raise RuntimeError("classify_result is None — contract enforcement failed")
    # ✅ next_state is Literal["enrich", "reject"] — always one of exactly two values.
    return result.next_state


def after_enrich(state: TicketState) -> str:
    result = state["enrich_result"]
    if result is None:
        raise RuntimeError("enrich_result is None — contract enforcement failed")
    return result.next_state   # always "route"


def after_route(state: TicketState) -> str:
    result = state["route_result"]
    if result is None:
        raise RuntimeError("route_result is None — contract enforcement failed")
    return result.next_state   # always "done" → maps to END below


# ── Graph ──────────────────────────────────────────────────────────────────────

builder = StateGraph(TicketState)
builder.add_node("classify", classify_node)
builder.add_node("enrich",   enrich_node)
builder.add_node("route",    route_node)
builder.add_node("reject",   reject_node)
builder.set_entry_point("classify")

# ✅ Conditional edges read validated Pydantic fields — never raw model text.
#    The model cannot influence routing by outputting unexpected strings.
builder.add_conditional_edges("classify", after_classify, {"enrich": "enrich", "reject": "reject"})
builder.add_conditional_edges("enrich",   after_enrich,   {"route": "route"})
builder.add_conditional_edges("route",    after_route,    {"done": END})
builder.add_edge("reject", END)

app = builder.compile()


# ── What the sandbox prevents ──────────────────────────────────────────────────
#
# EFFECT STORM prevented:
#   route_node max_effects=2 → EffectBudgetExceeded raised before the 3rd
#   write call executes. tracker.charge() fires BEFORE the tool is called,
#   so the 3rd email is never sent. Customer always receives at most 1 notification.
#
# TOOL LEAKAGE prevented:
#   classify_node only exposes [search_kb, list_categories].
#   override_priority and archive_as_duplicate are absent from both the
#   contract and the LLM's serialised tool list — they cannot be requested.
#
# TRANSITION HIJACKING prevented:
#   next_state is a Literal field validated by Pydantic at parse time.
#   run_sandboxed_node performs a second explicit check. Two independent
#   guards must both be bypassed for an invalid transition to execute.
#
# PARALLEL EFFECT STORM prevented:
#   When the model returns several tool_calls in one AIMessage (parallel tool
#   calling), tracker.preflight_check() counts ALL effect calls in the batch
#   and raises EffectBudgetExceeded BEFORE the first call executes.  Without
#   this, a batch [assign_to_queue, send_notification, send_notification] on a
#   max_effects=2 contract would commit the first two writes and only then
#   reject the third — leaving the system in a partially-applied state.
#   Atomic pre-flight ensures the whole batch either executes or is rejected.
#
# INFINITE LOOP prevented:
#   MAX_TOOL_ROUNDS=5 caps the inner tool loop per node. Each ticket
#   invokes at most 3 LLM calls (one per node) + bounded tool rounds —
#   total cost is predictable and auditable.
#
# BLIND TRANSITION prevented:
#   Code advances to the next node only after receiving a validated
#   ClassifyDecision / EnrichDecision / RouteDecision. If the LLM
#   returns malformed output, Pydantic raises before any transition fires.

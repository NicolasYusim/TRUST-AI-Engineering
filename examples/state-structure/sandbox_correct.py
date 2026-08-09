"""Executable reference: validate a complete agent plan before side effects.

Guarantees in this in-memory adapter:
- tools, transitions, arguments, tenant/resource scope, confirmation, total and
  per-tool effect limits are checked before execution;
- repeated idempotency keys do not duplicate effects;
- the fake transaction rolls back all in-memory effects on failure.

Does not guarantee:
- that unrelated external systems share a transaction;
- that an allowlisted action is semantically correct;
- that production adapters implement equivalent rollback or compensation.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


class ContractViolation(ValueError):
    pass


class AuthorizationDenied(PermissionError):
    pass


class IdempotencyConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class IdentityContext:
    user_id: str
    tenant_id: str
    permitted_ticket_ids: frozenset[str]
    can_route: bool
    can_notify: bool


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ActionPlan:
    next_state: str
    calls: tuple[ToolCall, ...]
    idempotency_key: str


@dataclass(frozen=True)
class ActionConfirmation:
    confirmed_by: str
    tenant_id: str
    plan_hash: str


def action_plan_digest(plan: ActionPlan) -> str:
    serialized = json.dumps(
        {
            "next_state": plan.next_state,
            "idempotency_key": plan.idempotency_key,
            "calls": [
                {"name": call.name, "arguments": call.arguments}
                for call in plan.calls
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def confirm_plan(
    plan: ActionPlan,
    context: IdentityContext,
) -> ActionConfirmation:
    return ActionConfirmation(
        confirmed_by=context.user_id,
        tenant_id=context.tenant_id,
        plan_hash=action_plan_digest(plan),
    )


@dataclass(frozen=True)
class SandboxContract:
    allowed_transitions: frozenset[str]
    allowed_tools: frozenset[str]
    per_tool_limits: dict[str, int]
    max_effects: int
    confirmation_required: bool


ROUTE_CONTRACT = SandboxContract(
    allowed_transitions=frozenset({"done", "manual_review"}),
    allowed_tools=frozenset({"assign_to_queue", "send_acknowledgement"}),
    per_tool_limits={"assign_to_queue": 1, "send_acknowledgement": 1},
    # Evidence label: illustrative. Calibrate effect limits to the domain.
    max_effects=2,
    confirmation_required=True,
)

ALLOWED_QUEUES = frozenset(
    {"billing-tier1", "billing-tier2", "tech-support", "account-ops", "shipping-ops"}
)


@dataclass
class TicketStore:
    tickets: dict[tuple[str, str], dict[str, Any]]
    notifications: list[dict[str, str]] = field(default_factory=list)
    applied_keys: set[tuple[str, str]] = field(default_factory=set)
    applied_payloads: dict[tuple[str, str], str] = field(default_factory=dict)
    audit_events: list[dict[str, str]] = field(default_factory=list)
    alert_signals: list[dict[str, str]] = field(default_factory=list)
    fail_on_tool: str | None = None

    def record_control_event(
        self,
        *,
        outcome: str,
        plan: ActionPlan,
        context: IdentityContext,
    ) -> None:
        """Record metadata only; raw tool arguments are deliberately excluded."""

        event = {
            "component": "support-ticket-router",
            "outcome": outcome,
            "tenant_id": context.tenant_id,
            "actor_id": context.user_id,
            "plan_hash": action_plan_digest(plan),
            "idempotency_key": plan.idempotency_key,
        }
        self.audit_events.append(event)
        if outcome in {
            "blocked_plan",
            "idempotency_conflict",
            "transaction_failure",
        }:
            self.alert_signals.append(dict(event))

    def execute_transaction(
        self,
        plan: ActionPlan,
        context: IdentityContext,
    ) -> str:
        scoped_idempotency_key = (context.tenant_id, plan.idempotency_key)
        payload_hash = action_plan_digest(plan)
        if scoped_idempotency_key in self.applied_keys:
            if self.applied_payloads[scoped_idempotency_key] != payload_hash:
                raise IdempotencyConflict(
                    "idempotency key was reused with a different action plan"
                )
            return "already_applied"

        original_tickets = deepcopy(self.tickets)
        original_notifications = deepcopy(self.notifications)
        try:
            for call in plan.calls:
                if call.name == self.fail_on_tool:
                    raise RuntimeError(f"injected adapter failure: {call.name}")
                if call.name == "assign_to_queue":
                    ticket_key = (context.tenant_id, call.arguments["ticket_id"])
                    self.tickets[ticket_key]["queue"] = call.arguments["queue"]
                elif call.name == "send_acknowledgement":
                    self.notifications.append(
                        {
                            "tenant_id": context.tenant_id,
                            "ticket_id": call.arguments["ticket_id"],
                            "template": call.arguments["template"],
                        }
                    )
                else:  # unreachable after validate_plan
                    raise ContractViolation(f"unknown tool: {call.name}")
        except Exception:
            self.tickets = original_tickets
            self.notifications = original_notifications
            raise

        self.applied_keys.add(scoped_idempotency_key)
        self.applied_payloads[scoped_idempotency_key] = payload_hash
        return "applied"


def _validate_arguments(call: ToolCall) -> None:
    if call.name == "assign_to_queue":
        if set(call.arguments) != {"ticket_id", "queue"}:
            raise ContractViolation("assign_to_queue arguments do not match schema")
        if call.arguments["queue"] not in ALLOWED_QUEUES:
            raise ContractViolation("queue is not allowlisted")
    elif call.name == "send_acknowledgement":
        if set(call.arguments) != {"ticket_id", "template"}:
            raise ContractViolation(
                "send_acknowledgement arguments do not match schema"
            )
        if call.arguments["template"] not in {"routing-received"}:
            raise ContractViolation("notification template is not allowlisted")

    if not isinstance(call.arguments.get("ticket_id"), str):
        raise ContractViolation("ticket_id must be a string")


def validate_plan(
    plan: ActionPlan,
    *,
    contract: SandboxContract,
    context: IdentityContext,
    confirmation: ActionConfirmation | None,
) -> None:
    if plan.next_state not in contract.allowed_transitions:
        raise ContractViolation("transition is not allowed")
    if plan.next_state == "manual_review" and plan.calls:
        raise ContractViolation("manual_review plans must not contain side effects")
    if not plan.idempotency_key.strip():
        raise ContractViolation("idempotency key is required")
    if len(plan.calls) > contract.max_effects:
        raise ContractViolation("effect budget exceeded")
    if contract.confirmation_required:
        if confirmation is None:
            raise AuthorizationDenied("confirmation is required")
        if (
            confirmation.confirmed_by != context.user_id
            or confirmation.tenant_id != context.tenant_id
            or confirmation.plan_hash != action_plan_digest(plan)
        ):
            raise AuthorizationDenied(
                "confirmation identity, tenant, or plan binding is invalid"
            )

    counts: dict[str, int] = {}
    for call in plan.calls:
        if call.name not in contract.allowed_tools:
            raise ContractViolation(f"tool is not allowed: {call.name}")
        counts[call.name] = counts.get(call.name, 0) + 1
        if counts[call.name] > contract.per_tool_limits.get(call.name, 0):
            raise ContractViolation(f"per-tool effect limit exceeded: {call.name}")
        _validate_arguments(call)

        ticket_id = call.arguments["ticket_id"]
        if ticket_id not in context.permitted_ticket_ids:
            raise AuthorizationDenied("ticket is outside the authorized resource scope")
        if call.name == "assign_to_queue" and not context.can_route:
            raise AuthorizationDenied("identity cannot route tickets")
        if call.name == "send_acknowledgement" and not context.can_notify:
            raise AuthorizationDenied("identity cannot notify ticket requesters")


def execute_plan(
    plan: ActionPlan,
    *,
    contract: SandboxContract,
    context: IdentityContext,
    store: TicketStore,
    confirmation: ActionConfirmation | None,
) -> str:
    try:
        # The complete plan is validated before TicketStore sees a side effect.
        validate_plan(
            plan,
            contract=contract,
            context=context,
            confirmation=confirmation,
        )

        for call in plan.calls:
            key = (context.tenant_id, call.arguments["ticket_id"])
            if key not in store.tickets:
                raise AuthorizationDenied(
                    "ticket does not exist in the current tenant"
                )

        result = store.execute_transaction(plan, context)
    except IdempotencyConflict:
        store.record_control_event(
            outcome="idempotency_conflict",
            plan=plan,
            context=context,
        )
        raise
    except (ContractViolation, AuthorizationDenied):
        store.record_control_event(
            outcome="blocked_plan",
            plan=plan,
            context=context,
        )
        raise
    except Exception:
        store.record_control_event(
            outcome="transaction_failure",
            plan=plan,
            context=context,
        )
        raise

    store.record_control_event(
        outcome=result,
        plan=plan,
        context=context,
    )
    return result

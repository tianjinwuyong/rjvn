"""MES-owned NG closed-loop transition guard.

This is a pure, append-only decision helper for station adapters. It validates
that an MES decision and required evidence exist; it never changes MES state.
"""

from enum import Enum
from typing import Any, Dict, Mapping


class ClosedLoopState(str, Enum):
    CONFIRMED_NG = "CONFIRMED_NG"
    REPAIR_ORDERED = "REPAIR_ORDERED"
    REPAIR_RECEIVED = "REPAIR_RECEIVED"
    REPAIRING = "REPAIRING"
    REPAIR_COMPLETE = "REPAIR_COMPLETE"
    RETEST_PENDING = "RETEST_PENDING"
    RETURN_PENDING = "RETURN_PENDING"
    CLOSED = "CLOSED"
    DISPOSITION_PENDING = "DISPOSITION_PENDING"


_TRANSITIONS = {
    (ClosedLoopState.CONFIRMED_NG, "CREATE_REPAIR_ORDER"): (ClosedLoopState.REPAIR_ORDERED, "HANDOVER_TO_REPAIR"),
    (ClosedLoopState.REPAIR_ORDERED, "RECEIVE_REPAIR"): (ClosedLoopState.REPAIR_RECEIVED, "START_REPAIR"),
    (ClosedLoopState.REPAIR_RECEIVED, "START_REPAIR"): (ClosedLoopState.REPAIRING, "RECORD_REPAIR_STEPS"),
    (ClosedLoopState.REPAIRING, "COMPLETE_REPAIR"): (ClosedLoopState.REPAIR_COMPLETE, "REQUEST_RETEST"),
    (ClosedLoopState.REPAIR_COMPLETE, "RETURN_TO_ICT"): (ClosedLoopState.RETEST_PENDING, "RECEIVE_AND_RETEST"),
    (ClosedLoopState.REPAIR_COMPLETE, "RETURN_TO_FCT"): (ClosedLoopState.RETEST_PENDING, "RECEIVE_AND_RETEST"),
    (ClosedLoopState.REPAIR_COMPLETE, "RETURN_TO_AGING"): (ClosedLoopState.RETEST_PENDING, "RECEIVE_AND_RETEST"),
    (ClosedLoopState.RETEST_PENDING, "RETEST_PASS"): (ClosedLoopState.RETURN_PENDING, "RECEIVE_RETURN"),
    (ClosedLoopState.RETEST_PENDING, "RETEST_NG"): (ClosedLoopState.DISPOSITION_PENDING, "MES_DECIDE_NEXT_ROUTE"),
    (ClosedLoopState.RETURN_PENDING, "RETURN_RECEIVED"): (ClosedLoopState.CLOSED, "RESUME_NORMAL_ROUTE"),
}


def apply_transition(state: ClosedLoopState, action: str, evidence: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate one transition and return an immutable transition fact."""

    try:
        current = state if isinstance(state, ClosedLoopState) else ClosedLoopState(str(state))
    except ValueError as exc:
        raise ValueError(f"unknown NG loop state: {state}") from exc
    action = str(action or "").upper()
    target = _TRANSITIONS.get((current, action))
    if not target:
        raise ValueError(f"transition not allowed: {current.value} -> {action}")
    required = ["eventId", "domainCode", "commandId"]
    if action not in {"RETEST_NG"}:
        required.append("mesDecisionId")
    if action == "CREATE_REPAIR_ORDER":
        required.append("workOrderId")
    if action.startswith("RETURN_TO_"):
        required.append("retestAuthorizationId")
    missing = [key for key in required if not evidence.get(key)]
    if missing:
        raise ValueError(f"MES evidence required: {', '.join(missing)}")
    result = {
        "authority": "MES",
        "agentMayMutateState": False,
        "eventId": str(evidence["eventId"]),
        "commandId": str(evidence["commandId"]),
        "domainCode": str(evidence["domainCode"]),
        "fromState": current.value,
        "action": action,
        "state": target[0].value,
        "nextAction": target[1],
        "mesDecisionId": evidence.get("mesDecisionId"),
        "workOrderId": evidence.get("workOrderId"),
        "retestAuthorizationId": evidence.get("retestAuthorizationId"),
        "preservedNgEventId": evidence.get("originalNgEventId"),
        "appendOnly": True,
        "feedbackStatus": "EXECUTED",
        "feedbackRequired": True,
        "feedbackEventType": "MES_COMMAND_FEEDBACK",
        # Identity fields travel with every immutable fact so the station and
        # PDA can render the complete repair-WO history without guessing.
        "workOrderId": evidence.get("workOrderId"),
        "repairWoId": evidence.get("repairWoId") or evidence.get("workOrderId"),
        "shipmentId": evidence.get("shipmentId"),
        "boxQr": evidence.get("boxQr") or evidence.get("stationQr"),
        "stationQr": evidence.get("stationQr") or evidence.get("boxQr"),
        "sns": list(evidence.get("sns") or []),
        "quantity": evidence.get("quantity"),
    }
    return result


def append_history(history: Any, transition_fact: Mapping[str, Any]) -> list:
    """Return a new append-only history list; never mutate or overwrite input."""
    prior = list(history or [])
    fact = dict(transition_fact)
    if not fact.get("eventId") or not fact.get("state"):
        raise ValueError("history fact requires eventId and state")
    if any(str(row.get("eventId")) == str(fact["eventId"]) for row in prior):
        return prior
    prior.append(fact)
    return prior

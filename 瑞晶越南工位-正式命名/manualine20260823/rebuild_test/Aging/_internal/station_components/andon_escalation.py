"""MES-owned Andon trigger evaluation.

The component evaluates observations only. It does not send notifications,
change routing, or close quality events; the MES consumes its append-only
decision and owns the escalation policy.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict


_LEVEL_ORDER = ("L0_INFO", "L1_LINE", "L2_SUPERVISOR", "L3_ENGINEERING", "L4_MANAGEMENT")
_MISMATCH_TRIGGERS = {"QUANTITY_MISMATCH", "SN_MISMATCH", "ROUTE_VIOLATION", "UNAUTHORIZED_ACTION"}


def _event_id(observation: Dict[str, Any]) -> str:
    stable = {
        "repairCaseId": observation.get("repairCaseId"),
        "workOrderId": observation.get("workOrderId"),
        "triggerType": observation.get("triggerType"),
        "occurredAtMs": observation.get("occurredAtMs"),
    }
    digest = hashlib.sha256(json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:24]
    return f"andon-{digest}"


def evaluate_andon(policy: Dict[str, Any], observation: Dict[str, Any]) -> Dict[str, Any]:
    """Return one append-only Andon projection for a measured observation."""

    trigger = str(observation.get("triggerType") or "UNKNOWN")
    now = int(observation.get("nowMs") or observation.get("occurredAtMs") or 0)
    occurred = int(observation.get("occurredAtMs") or now)
    current_status = str(observation.get("status") or "TRIGGERED")
    current_level = str(observation.get("currentSeverity") or "L0_INFO")
    levels = policy.get("levels") or {}
    level_key = "mismatch" if trigger in _MISMATCH_TRIGGERS else "pickup" if "PICKUP" in trigger else "default"
    severity = str(levels.get(level_key) or levels.get("default") or "L1_LINE")
    if severity not in _LEVEL_ORDER:
        severity = "L1_LINE"

    quantity_mismatch = (
        observation.get("expectedQuantity") is not None
        and observation.get("observedQuantity") is not None
        and observation["expectedQuantity"] != observation["observedQuantity"]
    )
    blocking = trigger in _MISMATCH_TRIGGERS or quantity_mismatch or bool(observation.get("blocking"))
    age_ms = max(0, now - occurred)
    grace_ms = max(0, int(policy.get("grace_ms") or 0))
    breach = blocking or age_ms >= grace_ms
    escalate_after_ms = max(0, int(policy.get("escalate_after_ms") or 0))
    should_escalate = current_status in {"ACKNOWLEDGED", "ASSIGNED", "IN_PROGRESS"} and age_ms >= escalate_after_ms

    result: Dict[str, Any] = {
        "andonEventId": _event_id(observation),
        "status": "ESCALATED" if should_escalate else "TRIGGERED" if breach else "PENDING",
        "severity": severity,
        "previousStatus": current_status if should_escalate else None,
        "previousSeverity": current_level if should_escalate else None,
        "nextAction": "ACKNOWLEDGE" if breach and not should_escalate else "ASSIGN" if should_escalate else "WAIT",
        "blocking": blocking,
        "triggerType": trigger,
        "ageMs": age_ms,
        "repairCaseId": observation.get("repairCaseId"),
        "workOrderId": observation.get("workOrderId"),
        "policyVersion": policy.get("policyVersion"),
        "feedbackRequired": True,
        "feedbackEventType": "ANDON_FEEDBACK",
        "feedbackStatus": "PENDING_ACK" if breach else "NOT_TRIGGERED",
        "observedAtMs": occurred,
    }
    return result

"""Single announcement contract for repair-station pickup."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, Mapping


CHANNELS = ["STATION", "TEAM_LEADER_PDA", "MES_KANBAN"]
FEEDBACK_STATUSES = {"RECEIVED", "CLAIMED", "COLLECTED", "REJECTED", "BLOCKED"}
DEFAULT_PICKUP_POLICY = {
    "policyVersion": "pickup-default-v1",
    "quantityThreshold": 10,
    "timeThresholdMinutes": 30,
    "humanButtonEnabled": True,
    "triggerMode": "ANY",
    "mesManaged": True,
}


def evaluate_pickup_trigger(policy: Mapping[str, Any], quantity: int, age_minutes: int, human_request: bool) -> Dict[str, Any]:
    """Evaluate the configurable OR trigger without sending an announcement."""
    quantity_threshold = max(1, int(policy.get("quantityThreshold") or 10))
    time_threshold = max(1, int(policy.get("timeThresholdMinutes") or 30))
    reasons = []
    if int(quantity or 0) >= quantity_threshold:
        reasons.append("QUANTITY_THRESHOLD")
    if int(age_minutes or 0) >= time_threshold:
        reasons.append("TIME_THRESHOLD")
    if bool(human_request) and bool(policy.get("humanButtonEnabled", True)):
        reasons.append("HUMAN_REQUEST")
    return {
        "ready": bool(reasons),
        "reasons": reasons,
        "policyVersion": policy.get("policyVersion", ""),
        "triggerMode": policy.get("triggerMode", "ANY"),
        "mesManaged": True,
    }


def _command_id(data: Mapping[str, Any]) -> str:
    stable = {key: data.get(key) for key in ("domainCode", "workOrderId", "eventId", "bucketQr")}
    digest = hashlib.sha256(json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:20]
    return f"pickup-{digest}"


def pickup_alarm_id(command_id: str, alarm_type: str = "NG_PICKUP") -> str:
    """Return the stable MES alarm identity for a pickup/revival command."""
    command = str(command_id or "").strip()
    if not command:
        raise ValueError("pickup alarm requires commandId")
    return f"{str(alarm_type or 'NG_PICKUP').upper()}:{command}"


def build_pickup_announcement(data: Mapping[str, Any]) -> Dict[str, Any]:
    required = ("domainCode", "lineCode", "repairStation", "sourceStation", "workOrderId", "eventId", "bucketQr", "sns", "destinationStation")
    missing = [key for key in required if not data.get(key)]
    if missing:
        raise ValueError(f"pickup announcement missing: {', '.join(missing)}")
    sns = [str(sn).strip() for sn in data["sns"] if str(sn).strip()]
    if not sns:
        raise ValueError("pickup announcement requires at least one SN")
    now = int(data.get("createdAtMs") or time.time() * 1000)
    command_id = str(data.get("commandId") or _command_id(data))
    return {
        "eventType": "NG_PICKUP_ANNOUNCEMENT",
        "commandId": command_id,
        "alarmId": pickup_alarm_id(command_id),
        "eventId": str(data["eventId"]),
        "domainCode": str(data["domainCode"]),
        "lineCode": str(data["lineCode"]),
        "repairStation": str(data["repairStation"]),
        "sourceStation": str(data["sourceStation"]),
        "destinationStation": str(data["destinationStation"]),
        "batchId": str(data["batchId"]) if data.get("batchId") else None,
        "workOrderId": str(data["workOrderId"]),
        "bucketQr": str(data["bucketQr"]),
        "sns": sns,
        "quantity": len(sns),
        "channels": list(CHANNELS),
        "recipientRoles": ["LINE_LEADER", "TEAM_LEADER"],
        "status": "READY_FOR_PICKUP",
        "createdAtMs": now,
        "feedbackRequired": True,
        "policyVersion": str(data.get("policyVersion") or DEFAULT_PICKUP_POLICY["policyVersion"]),
        "triggerReasons": list(data.get("triggerReasons") or []),
        "appendOnly": True,
    }


def build_pickup_feedback(announcement: Mapping[str, Any], status: str, actor: str, reason: str = "") -> Dict[str, Any]:
    status = str(status or "").upper()
    if status not in FEEDBACK_STATUSES:
        raise ValueError(f"unsupported pickup feedback: {status}")
    if not actor:
        raise ValueError("pickup feedback requires actor")
    return {
        "eventType": "NG_PICKUP_FEEDBACK",
        "commandId": str(announcement["commandId"]),
        "announcementEventId": str(announcement["eventId"]),
        "domainCode": str(announcement["domainCode"]),
        "workOrderId": str(announcement["workOrderId"]),
        "bucketQr": str(announcement["bucketQr"]),
        "feedbackStatus": status,
        "alarmId": pickup_alarm_id(str(announcement["commandId"])),
        "actor": str(actor),
        "reason": str(reason or ""),
        "occurredAtMs": int(time.time() * 1000),
        "appendOnly": True,
    }

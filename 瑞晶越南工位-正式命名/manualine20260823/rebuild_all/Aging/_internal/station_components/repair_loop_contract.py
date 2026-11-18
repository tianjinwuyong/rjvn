"""Small, append-only contracts shared by 2D repair-loop adapters.

These helpers validate facts at the edge; MES remains the authority for route,
permissions, retest limits, and final disposition.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Iterable, Mapping, Optional


def _required(data: Mapping[str, Any], keys: Iterable[str]) -> None:
    missing = [key for key in keys if not data.get(key)]
    if missing:
        raise ValueError("required: " + ", ".join(missing))


def build_pickup_ack(announcement: Mapping[str, Any], actor: str, scanned_qr: str) -> Dict[str, Any]:
    _required(announcement, ("eventId", "workOrderId", "bucketQr"))
    if not actor or not scanned_qr:
        raise ValueError("pickup acknowledgement requires actor and scan")
    if str(scanned_qr).strip() != str(announcement["bucketQr"]).strip():
        raise ValueError("bucket QR does not match announcement")
    return {
        "eventType": "NG_PICKUP_ACKNOWLEDGED",
        "eventId": str(announcement["eventId"]),
        "workOrderId": str(announcement["workOrderId"]),
        "bucketQr": str(announcement["bucketQr"]),
        "actor": str(actor),
        "status": "CLAIMED",
        "appendOnly": True,
    }


def build_repair_evidence(work_order_id: str, event_id: str, operator: str,
                          steps: Iterable[Mapping[str, Any]], *, materials: Optional[Iterable[Mapping[str, Any]]] = None,
                          attachments: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    if not work_order_id or not event_id or not operator:
        raise ValueError("repair evidence requires work order, event, and operator")
    step_list = [dict(step) for step in steps]
    if not step_list:
        raise ValueError("repair evidence requires at least one step")
    return {
        "eventType": "REPAIR_EVIDENCE_RECORDED",
        "eventId": str(event_id),
        "workOrderId": str(work_order_id),
        "operator": str(operator),
        "steps": step_list,
        "materials": [dict(item) for item in (materials or [])],
        "attachments": [str(item) for item in (attachments or [])],
        "appendOnly": True,
    }


def evaluate_sla(received_at_minutes: int, now_minutes: int, limit_minutes: int) -> Dict[str, Any]:
    elapsed = max(0, int(now_minutes) - int(received_at_minutes))
    limit = max(1, int(limit_minutes))
    return {"elapsedMinutes": elapsed, "limitMinutes": limit,
            "status": "BREACHED" if elapsed >= limit else "ON_TRACK"}


def build_return_handover(work_order_id: str, destination_station: str,
                          retest_authorization_id: str, sns: Iterable[str], shipment_id: str) -> Dict[str, Any]:
    if not work_order_id or not destination_station or not retest_authorization_id or not shipment_id:
        raise ValueError("return handover requires work order, destination, authorization, and shipment")
    clean_sns = [str(sn).strip() for sn in sns if str(sn).strip()]
    if not clean_sns:
        raise ValueError("return handover requires SNs")
    return {
        "eventType": "REPAIR_RETURN_HANDOVER",
        "workOrderId": str(work_order_id),
        "destinationStation": str(destination_station),
        "retestAuthorizationId": str(retest_authorization_id),
        "shipmentId": str(shipment_id),
        "sns": clean_sns,
        "quantity": len(clean_sns),
        "appendOnly": True,
    }


def append_outbox(outbox: Iterable[Mapping[str, Any]], event: Mapping[str, Any]) -> list:
    event_id = str(event.get("eventId") or "").strip()
    if not event_id:
        raise ValueError("outbox event requires eventId")
    result = [dict(item) for item in (outbox or [])]
    if any(str(item.get("eventId")) == event_id for item in result):
        return result
    item = dict(event)
    item.setdefault("queuedAtMs", int(time.time() * 1000))
    item.setdefault("replayStatus", "PENDING")
    result.append(item)
    return result

"""Shared MES-owned repair WO lifecycle graph for all station Agents.

The graph is a read-only projection of MES facts. Agents may render it and
report evidence, but only MES may advance or reverse a node.
"""

from __future__ import annotations

NODES = (
    "WO_INFORMING",
    "SUPERVISOR_ACKNOWLEDGED",
    "SENT_TO_REPAIR",
    "REPAIRING",
    "PICKUP_REQUESTED",
    "SENT_TO_SOURCE_STATION",
    "REVIVED",
)

EDGES = tuple(zip(NODES, NODES[1:]))

STATUS_TO_NODE = {
    "CREATED": "WO_INFORMING",
    "WAITING_REPAIR": "SENT_TO_REPAIR",
    "REPAIR_RECEIVED": "REPAIRING",
    "REPAIR_IN_PROGRESS": "REPAIRING",
    "REPAIR_COMPLETED": "PICKUP_REQUESTED",
    "RETURN_PENDING": "SENT_TO_SOURCE_STATION",
    "CLOSED_RETEST_PASS": "REVIVED",
    "DONE": "REVIVED",
    "REVIVED": "REVIVED",
}


def cycle_projection(work_order: dict) -> dict:
    """Return a stable, render-ready projection without changing the WO."""
    status = str(work_order.get("status") or "UNKNOWN").upper()
    current = STATUS_TO_NODE.get(status, "WO_INFORMING")
    return {
        "workOrderNo": work_order.get("repairWorkOrderNo") or work_order.get("workOrderNo") or work_order.get("id"),
        "status": status,
        "currentNode": current,
        "nodes": [{"id": node, "active": node == current} for node in NODES],
        "edges": [{"from": source, "to": target} for source, target in EDGES],
        "timestamps": {key: work_order.get(key) for key in (
            "issuedAt", "acknowledgedAt", "sentToRepairAt", "repairStartedAt",
            "pickupRequestedAt", "returnedAt", "revivedAt",
        ) if work_order.get(key)},
    }


__all__ = ["NODES", "EDGES", "STATUS_TO_NODE", "cycle_projection"]

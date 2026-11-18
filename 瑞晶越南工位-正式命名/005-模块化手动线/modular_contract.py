from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

NG_ACTIONS = {"MARK_ONLY", "STOP_AND_HOLD", "REMOVE_IMMEDIATELY", "SEND_REPAIR"}
RETURN_ROUTES = {"ORIGIN", "MES_CALCULATED", "CONTINUE_WITH_NG_ATTRIBUTE", "REPEAT_AGING"}


@dataclass(frozen=True)
class RepairPolicy:
    key: str
    action_mode: str
    retest_limit: int
    repair_destination: str
    return_route: str
    receipt_sla_minutes: int
    repair_sla_minutes: int
    escalation_minutes: List[int] = field(default_factory=list)
    max_repair_attempts: int = 2
    offline_policy: str = "BLOCK"
    policy_version: str = "local-fallback-1"

    def validate(self) -> None:
        if self.action_mode not in NG_ACTIONS:
            raise ValueError("Unsupported NG action: " + self.action_mode)
        if self.return_route not in RETURN_ROUTES:
            raise ValueError("Unsupported return route: " + self.return_route)
        if self.retest_limit < 0 or self.max_repair_attempts < 0:
            raise ValueError("Retest/repair limits cannot be negative")
        if self.receipt_sla_minutes < 1 or self.repair_sla_minutes < 1:
            raise ValueError("SLA minutes must be positive")


@dataclass(frozen=True)
class StationDefinition:
    sequence: int
    code: str
    name_zh: str
    name_en: str
    adapter: str
    inputs: List[str]
    normal_next: str
    ng_policy: RepairPolicy


@dataclass
class StationViewModel:
    station: StationDefinition
    product_sn: str = ""
    work_order: str = ""
    operator: str = "--"
    gate: str = "UNKNOWN"
    gate_reason: str = "Waiting for MES product gate"
    result: str = "IDLE"
    next_action: str = "Scan product"
    alarm: str = "No new alarm"
    health: Dict[str, str] = field(default_factory=lambda: {
        "Scanner": "READY", "Equipment": "PREVIEW", "MES": "READ ONLY",
        "Outbox": "0", "Clock": "OK", "Agent": "MODULAR-1.0"
    })


def merge_policy(key: str, specific: Dict[str, Any], defaults: Dict[str, Any]) -> RepairPolicy:
    merged = dict(defaults)
    merged.update(specific)
    policy = RepairPolicy(
        key=key,
        action_mode=str(merged.get("actionMode", "STOP_AND_HOLD")).upper(),
        retest_limit=int(merged.get("retestLimit", 0)),
        repair_destination=str(merged.get("repairDestination", "manual_rework")),
        return_route=str(merged.get("returnRoute", "MES_CALCULATED")).upper(),
        receipt_sla_minutes=int(merged.get("receiptSlaMinutes", 30)),
        repair_sla_minutes=int(merged.get("repairSlaMinutes", 120)),
        escalation_minutes=[int(value) for value in merged.get("escalationMinutes", [30, 60, 120, 180])],
        max_repair_attempts=int(merged.get("maxRepairAttempts", 2)),
        offline_policy=str(merged.get("offlinePolicy", "BLOCK")).upper(),
        policy_version=str(merged.get("version", "local-fallback-1")),
    )
    policy.validate()
    return policy

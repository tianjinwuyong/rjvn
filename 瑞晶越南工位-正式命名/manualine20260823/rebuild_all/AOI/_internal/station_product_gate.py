# -*- coding: utf-8 -*-
"""Thin Station-Agent client for the MES-owned Product Gate."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass


VALID_GATE_STATES = {"ALLOW", "HOLD", "REJECT", "REPAIR_ROUTE", "COMPLETED"}


class ProductGateUnavailable(RuntimeError):
    """No authoritative MES decision was received; station work must stay blocked."""


@dataclass(frozen=True)
class ProductGateDecision:
    decision_id: str
    gate_state: str
    allowed: bool
    reason_code: str
    next_action: str
    product_id: str = ""
    destination_station_code: str = ""
    route_revision: str = ""
    replay: bool = False


class ProductGateClient:
    def __init__(self, mes_base_url, station_code, agent_id, host_ip, timeout_seconds=4, opener=None):
        self.endpoint = str(mes_base_url).rstrip("/") + "/api/mes/product-gate/evaluate"
        self.station_code = str(station_code).strip().lower()
        self.agent_id = str(agent_id).strip()
        self.host_ip = str(host_ip).strip()
        self.timeout_seconds = max(1, int(timeout_seconds))
        self.opener = opener or urllib.request.urlopen
        if not self.station_code or not self.agent_id or not self.host_ip:
            raise ValueError("station_code, agent_id and host_ip are required")

    def evaluate(self, *, identifier, operator_id, occurred_at, idempotency_key,
                 identifier_type="", work_order_code=""):
        payload = {
            "identifier": str(identifier).strip().upper(),
            "identifierType": str(identifier_type).strip().upper() or None,
            "stationCode": self.station_code,
            "workOrderCode": str(work_order_code).strip() or None,
            "operatorId": str(operator_id).strip(),
            "agentId": self.agent_id,
            "hostIp": self.host_ip,
            "occurredAt": str(occurred_at).strip(),
            "idempotencyKey": str(idempotency_key).strip(),
        }
        required = (payload["identifier"], payload["operatorId"], payload["occurredAt"], payload["idempotencyKey"])
        if not all(required):
            raise ValueError("identifier, operator_id, occurred_at and idempotency_key are required")
        request = urllib.request.Request(self.endpoint, data=json.dumps(payload).encode("utf-8"),
                                         headers={"Content-Type": "application/json"}, method="POST")
        try:
            response = self.opener(request, timeout=self.timeout_seconds)
            raw = response.read()
        except urllib.error.HTTPError as error:
            if error.code != 409:
                raise ProductGateUnavailable(f"MES Product Gate HTTP {error.code}") from error
            raw = error.read()
        except Exception as error:
            raise ProductGateUnavailable(f"MES Product Gate unavailable: {error}") from error
        try:
            body = json.loads(raw.decode("utf-8"))
            item = body["decision"]
            state = str(item["gateState"]).upper()
            if state not in VALID_GATE_STATES:
                raise ValueError("unknown gate state")
            return ProductGateDecision(
                decision_id=str(item.get("decisionId") or ""), gate_state=state,
                allowed=state == "ALLOW" and bool(item.get("allowed", True)),
                reason_code=str(item.get("reasonCode") or ""),
                next_action=str(item.get("nextAction") or ""),
                product_id=str(item.get("productId") or ""),
                destination_station_code=str(item.get("destinationStationCode") or ""),
                route_revision=str(item.get("routeRevision") or ""),
                replay=bool(body.get("replay")),
            )
        except Exception as error:
            raise ProductGateUnavailable("MES Product Gate returned an invalid decision") from error


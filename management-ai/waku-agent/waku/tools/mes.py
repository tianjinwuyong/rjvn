"""Read-only MES tools exposed as an optional Waku plugin.

The plugin boundary is deliberately small: Waku can inspect MES state, but
cannot mutate work orders, bindings, or material records through this adapter.
Writes remain in the MES UI/API workflows where approval and audit controls
already exist.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from waku.tools.registry import Tool


def _get(base_url: str, token: str, path: str, query: dict[str, object]) -> str:
    base = base_url.rstrip("/")
    url = f"{base}/{path.lstrip('/')}"
    if query:
        url += "?" + urllib.parse.urlencode(query)
    request = urllib.request.Request(url, method="GET")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return f"MES read failed ({exc.code}): {exc.reason}"
    except (urllib.error.URLError, TimeoutError) as exc:
        return f"MES read unavailable: {exc}"
    try:
        return json.dumps(json.loads(payload), ensure_ascii=False)
    except json.JSONDecodeError:
        return payload[:20_000]


def make_tools(base_url: str, token: str = "") -> list[Tool]:
    """Build read-only MES tools when ``MES_API_BASE_URL`` is configured.

    The manager snapshot is intentionally an aggregation of GET requests. It
    gives a manager agent situational awareness without granting it a write
    path into MES.
    """

    def list_work_orders(status: str = "released", limit: int = 20) -> str:
        safe_limit = max(1, min(int(limit), 100))
        return _get(base_url, token, "/pmc/work-orders", {"status": status, "limit": safe_limit})

    def list_active_boms(limit: int = 50) -> str:
        safe_limit = max(1, min(int(limit), 100))
        return _get(base_url, token, "/boms", {"status": "active", "limit": safe_limit})

    def factory_manager_snapshot(limit: int = 20) -> str:
        """Collect a bounded, read-only view for the factory manager."""
        safe_limit = max(1, min(int(limit), 50))
        reads = {
            "workOrders": _get(base_url, token, "/pmc/work-orders", {
                "status": "active", "limit": safe_limit,
            }),
            "lines": _get(base_url, token, "/mes/lines", {"limit": safe_limit}),
            "events": _get(base_url, token, "/mes/events", {"limit": safe_limit}),
            "materialLots": _get(base_url, token, "/wms/material-lots", {
                "page": 1, "pageSize": safe_limit,
            }),
        }
        return json.dumps(reads, ensure_ascii=False)

    return [
        Tool(
            name="mes_list_work_orders",
            description="Read released or active work orders from MES. Read-only; never creates or changes a work order.",
            input_schema={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "MES status filter, e.g. released or active"},
                    "limit": {"type": "integer", "description": "Maximum rows (1-100)"},
                },
                "required": [],
            },
            fn=list_work_orders,
        ),
        Tool(
            name="mes_list_active_boms",
            description="Read active BOMs from MES for planning and retrieval. Read-only.",
            input_schema={
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "Maximum rows (1-100)"}},
                "required": [],
            },
            fn=list_active_boms,
        ),
        Tool(
            name="mes_factory_manager_snapshot",
            description=(
                "Read a bounded real-time factory snapshot for the manager: active work orders, "
                "line status, recent MES events, and material lots. Read-only; never authorizes "
                "or performs a production action."
            ),
            input_schema={
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "Maximum rows per source (1-50)"}},
                "required": [],
            },
            fn=factory_manager_snapshot,
        ),
    ]

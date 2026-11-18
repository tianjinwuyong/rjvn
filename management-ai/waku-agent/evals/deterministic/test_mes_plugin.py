from __future__ import annotations

import json

from waku.tools import mes


def test_mes_plugin_is_read_only_and_registers_manager_snapshot():
    tools = mes.make_tools("http://mes.local/api", "token")
    assert [tool.name for tool in tools] == [
        "mes_list_work_orders", "mes_list_active_boms", "mes_factory_manager_snapshot"
    ]
    assert all("read-only" in tool.description.lower() for tool in tools)
    assert all(set(tool.input_schema["properties"]) <= {"status", "limit"} for tool in tools)


def test_mes_tool_clamps_limit_and_serializes_response(monkeypatch):
    seen = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"items": []}).encode()

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        return Response()

    monkeypatch.setattr(mes.urllib.request, "urlopen", fake_urlopen)
    result = mes.make_tools("http://mes.local/api")[0].fn(limit=999)
    assert json.loads(result) == {"items": []}
    assert "limit=100" in seen["url"]
    assert seen["timeout"] == 8


def test_factory_manager_snapshot_is_bounded_and_read_only(monkeypatch):
    seen = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"items": []}).encode()

    def fake_urlopen(request, timeout):
        seen.append(request.full_url)
        return Response()

    monkeypatch.setattr(mes.urllib.request, "urlopen", fake_urlopen)
    snapshot = mes.make_tools("http://mes.local/api")[2].fn(limit=999)
    payload = json.loads(snapshot)
    assert set(payload) == {"workOrders", "lines", "events", "materialLots"}
    assert len(seen) == 4
    assert all("limit=50" in url or "pageSize=50" in url for url in seen)

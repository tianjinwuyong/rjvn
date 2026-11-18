from __future__ import annotations

from typing import Any, Dict

import httpx
from prime_cli.api.brainoutside import BrainOutsideClient


def test_brainoutside_client_uses_configured_url_and_bearer(monkeypatch):
    seen: Dict[str, Any] = {}

    class DummyHTTPClient:
        def __init__(self, **kwargs: Any) -> None:
            seen["headers"] = kwargs["headers"]

        def post(self, url: str, json: Dict[str, Any]) -> httpx.Response:
            seen["url"] = url
            seen["json"] = json
            request = httpx.Request("POST", url)
            return httpx.Response(200, request=request, json={"pong": True})

    monkeypatch.setattr("prime_cli.api.brainoutside.httpx.Client", DummyHTTPClient)
    client = BrainOutsideClient(
        base_url="http://brain.test/",
        api_key="brain-test-key",
    )

    assert client.ping() == {"pong": True}
    assert seen["url"] == "http://brain.test/api/v1/ping"
    assert seen["json"] == {}
    assert seen["headers"]["Authorization"] == "Bearer brain-test-key"


def test_brainoutside_client_builds_context_request(monkeypatch):
    seen: Dict[str, Any] = {}

    class DummyHTTPClient:
        def __init__(self, **kwargs: Any) -> None:
            pass

        def post(self, url: str, json: Dict[str, Any]) -> httpx.Response:
            seen["url"] = url
            seen["json"] = json
            request = httpx.Request("POST", url)
            return httpx.Response(200, request=request, json={"context_pack": "rules"})

    monkeypatch.setattr("prime_cli.api.brainoutside.httpx.Client", DummyHTTPClient)

    result = BrainOutsideClient(api_key="key").assemble_context(
        "Find the ICT repair rule", lens="manual-line"
    )

    assert result == {"context_pack": "rules"}
    assert seen["url"].endswith("/api/v1/assemble-context")
    assert seen["json"] == {"task": "Find the ICT repair rule", "lens": "manual-line"}

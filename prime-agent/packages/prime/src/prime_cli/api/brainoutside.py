"""Read-only client for an optional BrainOutside knowledge server."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx


class BrainOutsideError(RuntimeError):
    """Raised when BrainOutside cannot answer a read request."""


def _error_message(response: httpx.Response) -> str:
    text = response.text.strip()
    return text or response.reason_phrase or "Unknown error"


class BrainOutsideClient:
    """Small, read-only client for BrainOutside's v1 REST endpoints."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (
            base_url or os.getenv("BRAINOUTSIDE_URL", "http://localhost:8000")
        ).rstrip("/")
        self.api_key = api_key or os.getenv("BRAINOUTSIDE_API_KEY") or os.getenv(
            "BRAINOUTSIDE_MCP_KEY", ""
        )
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        self._client = httpx.Client(headers=headers, timeout=timeout)

    def _post(self, slug: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/api/v1/{slug}"
        response = self._client.post(url, json=payload or {})
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise BrainOutsideError(
                f"POST {url} failed: {response.status_code} {_error_message(response)}"
            ) from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise BrainOutsideError(f"POST {url} returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise BrainOutsideError(f"POST {url} returned a non-object response")
        return data

    def ping(self) -> Dict[str, Any]:
        return self._post("ping")

    def get_index(self) -> Dict[str, Any]:
        return self._post("get-index")

    def list_notes(
        self,
        *,
        kind: str = "",
        topic: str = "",
        project: str = "",
        status: str = "current",
    ) -> Dict[str, Any]:
        return self._post(
            "list-notes",
            {"kind": kind, "topic": topic, "project": project, "status": status},
        )

    def get_note(self, entity_id: str) -> Dict[str, Any]:
        return self._post("get-note", {"entity_id": entity_id})

    def assemble_context(self, task: str, *, lens: str = "") -> Dict[str, Any]:
        return self._post("assemble-context", {"task": task, "lens": lens})

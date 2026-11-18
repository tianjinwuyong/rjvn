"""Read-only factory-manager monitoring and task generation.

The monitor never changes MES/WMS state. It periodically reads the same
bounded endpoints exposed to the manager agent and stores actionable tasks in
the Waku home directory for the dashboard to display.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from waku.config import load_settings
from waku.tools.mes import _get


class FactoryManagerMonitor:
    def __init__(self, interval_seconds: int | None = None) -> None:
        self.interval = max(30, int(interval_seconds or os.getenv("FACTORY_MANAGER_INTERVAL", "300")))
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_run = ""
        self._last_error = ""
        self._tasks: list[dict[str, Any]] = []

    @property
    def path(self) -> Path:
        settings = load_settings()
        settings.ensure_home()
        return settings.home / "factory_manager_tasks.json"

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._load()
        self._thread = threading.Thread(target=self._loop, name="factory-manager-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _loop(self) -> None:
        self.run_once()
        while not self._stop.wait(self.interval):
            self.run_once()

    def _load(self) -> None:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            with self._lock:
                self._tasks = payload.get("tasks", [])[-200:]
                self._last_run = payload.get("lastRun", "")
        except (OSError, ValueError):
            pass

    def _save(self) -> None:
        payload = {"lastRun": self._last_run, "lastError": self._last_error, "tasks": self._tasks[-200:]}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _json(text: str) -> dict[str, Any] | list[Any] | None:
        try:
            return json.loads(text)
        except (TypeError, ValueError):
            return None

    def run_once(self) -> dict[str, Any]:
        base = os.getenv("MES_API_BASE_URL", "").strip()
        token = os.getenv("MES_API_TOKEN", "").strip()
        now = datetime.now(UTC).isoformat()
        if not base:
            with self._lock:
                self._last_run, self._last_error = now, "MES_API_BASE_URL is not configured"
                self._save()
            return self.status()

        reads = {
            "workOrders": _get(base, token, "/pmc/work-orders", {"status": "active", "limit": 50}),
            "lines": _get(base, token, "/mes/lines", {"limit": 50}),
            "events": _get(base, token, "/mes/events", {"limit": 50}),
            "materialLots": _get(base, token, "/wms/material-lots", {"page": 1, "pageSize": 50}),
        }
        generated: list[dict[str, Any]] = []
        for source, raw in reads.items():
            if raw.startswith("MES read failed") or raw.startswith("MES read unavailable"):
                generated.append({
                    "type": "MES_READ_FAILURE", "source": source, "owner": "it",
                    "priority": "high", "status": "open", "title": f"MES {source} read failed",
                    "detail": raw, "createdAt": now,
                })
        lines = self._json(reads["lines"])
        if isinstance(lines, dict):
            items = ((lines.get("data") or {}).get("items") or [])
            for line in items:
                if str(line.get("status", "")).lower() not in {"running", "active"}:
                    generated.append({
                        "type": "LINE_NOT_RUNNING", "source": line.get("lineCode", ""),
                        "owner": "line_manager", "priority": "high", "status": "open",
                        "title": f"Line {line.get('lineCode', '?')} is not running",
                        "detail": line.get("status", "unknown"), "createdAt": now,
                    })

        with self._lock:
            # Deduplicate open tasks by type/source, while keeping history.
            existing = {(t.get("type"), t.get("source")): t for t in self._tasks if t.get("status") == "open"}
            for task in generated:
                key = (task["type"], task.get("source"))
                if key not in existing:
                    self._tasks.append(task)
            self._last_run, self._last_error = now, ""
            self._save()
        return self.status()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {"lastRun": self._last_run, "lastError": self._last_error,
                    "intervalSeconds": self.interval,
                    "running": bool(self._thread and self._thread.is_alive()),
                    "tasks": list(self._tasks[-200:])}


_monitor: FactoryManagerMonitor | None = None


def get_monitor() -> FactoryManagerMonitor:
    global _monitor
    if _monitor is None:
        _monitor = FactoryManagerMonitor()
        _monitor.start()
    return _monitor

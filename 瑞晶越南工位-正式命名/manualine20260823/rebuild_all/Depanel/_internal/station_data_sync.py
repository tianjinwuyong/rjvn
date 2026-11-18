# -*- coding: utf-8 -*-
"""Shared, fail-closed MES scan gate for manual-line station agents."""
import json
import threading
import time
import urllib.error
import urllib.request
import uuid


def _event_url(value):
    text = str(value or "").rstrip("/")
    if "/api/" in text:
        return text if text.endswith("/api/pda/events") else text.split("/api/")[0] + "/api/pda/events"
    return text + "/api/pda/events"


def _read_error(exc):
    try:
        raw = exc.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


def mes_scan_gate(mes_url, station_code, sn, event_type="physical_scanner", timeout=6, **detail):
    """Ask MES for the authoritative pre-scan decision.

    Returns ``(allowed, decision)``. Any timeout, malformed response, or MES
    error is fail-closed, exactly like an explicit MES rejection.
    """
    normalized = str(sn or "").strip().upper()
    if not normalized:
        return False, {"ok": False, "blocked": True, "code": "EMPTY_SN"}
    payload = {
        "eventId": str(uuid.uuid4()),
        "from": station_code,
        "to": "mes_server",
        "type": "SCAN_GUARD_CHECK",
        "stationCode": station_code,
        "priority": "critical",
        "payload": {"sn": normalized, "result": "READ", "eventType": event_type, **detail},
    }
    request = urllib.request.Request(
        _event_url(mes_url), data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=float(timeout)) as response:
            decision = json.loads(response.read().decode("utf-8") or "{}")
        blocked = bool(decision.get("blocked")) or decision.get("ok") is False
        return not blocked, decision
    except urllib.error.HTTPError as exc:
        decision = _read_error(exc)
        if not isinstance(decision, dict):
            decision = {}
        decision.setdefault("ok", False); decision.setdefault("blocked", True)
        decision.setdefault("code", decision.get("error", {}).get("code") or f"MES_HTTP_{exc.code}")
        return False, decision
    except Exception as exc:
        return False, {"ok": False, "blocked": True, "code": "MES_GUARD_UNAVAILABLE", "message": str(exc)}


class ConfirmedNgGuard:
    """Small local cache; synchronous ``mes_scan_gate`` remains authoritative."""
    def __init__(self, _db_path, mes_url, refresh_seconds=10):
        self.url = str(mes_url).split("/api/")[0].rstrip("/") + "/api/station/ng-guard"
        self.refresh_seconds = refresh_seconds
        self.items = {}
        self.last_refresh = 0
        self.lock = threading.RLock()

    def refresh(self):
        try:
            with urllib.request.urlopen(self.url, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
            rows = data.get("items") or data.get("ng") or data if isinstance(data, list) else []
            with self.lock:
                self.items = {str(x.get("sn") or "").strip().upper(): x for x in rows if x.get("sn")}
                self.last_refresh = time.time()
            return len(self.items)
        except Exception:
            return 0

    def contains(self, sn):
        if time.time() - self.last_refresh > self.refresh_seconds:
            self.refresh()
        with self.lock:
            return str(sn or "").strip().upper() in self.items

    def get(self, sn, default=None):
        with self.lock:
            return self.items.get(str(sn or "").strip().upper(), default)


class ExpectedSnManifest:
    def __init__(self, *_args, **_kwargs):
        self.items = set()
    def contains(self, sn):
        return str(sn or "").strip().upper() in self.items
    def refresh(self, *_args, **_kwargs):
        return 0


class DurableMesSync:
    """Compatibility holder for agents with their own durable SQLite outbox."""
    def __init__(self, *_args, **_kwargs):
        self.ng_guard = ConfirmedNgGuard(None, _kwargs.get("mes_url", ""))
    def sync_once(self, *_args, **_kwargs):
        return 0
    def flush(self):
        return None


def reconcile_inventory(*_args, **_kwargs):
    return 0


def start_sync_worker(*_args, **_kwargs):
    return None


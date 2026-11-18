# -*- coding: utf-8 -*-
"""Direct MES SN/NG guards used by every station.

The station scan path deliberately does not depend on a second local server.
MES 155 is primary and MES 122 is the configured fallback.  Accepted scans
are registered in the station's own SQLite by the common agent; production
events continue through the normal MES outbox.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


PRIMARY = os.environ.get("MES_PRIMARY_URL", "http://192.168.6.155:8080").rstrip("/")
BACKUP = os.environ.get("MES_BACKUP_URL", "http://192.168.6.122:8080").rstrip("/")
MES_BASES = tuple(dict.fromkeys((PRIMARY, BACKUP)))
MES_OPERATOR = os.environ.get("MES_OPERATOR", "QC_VN_01").strip()
MES_PASSWORD = os.environ.get("MES_PASSWORD", "Factory@123")
REQUIRE_SERVICE = os.environ.get("STATION_REQUIRE_NG_SYNC", "1").lower() not in {"0", "false", "no"}
_token_lock = threading.Lock()
_tokens: dict[str, tuple[str, float]] = {}


def _json_request(base: str, method: str, path: str, payload=None, token: str = "", timeout=2.5):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        value = json.loads(response.read().decode("utf-8") or "{}")
    return value if isinstance(value, dict) else {}


def _login(base: str) -> str:
    now = time.time()
    with _token_lock:
        cached = _tokens.get(base)
        if cached and cached[1] > now + 30:
            return cached[0]
    result = _json_request(base, "POST", "/auth/login", {
        "username": MES_OPERATOR, "password": MES_PASSWORD,
    })
    data = result.get("data") if isinstance(result.get("data"), dict) else result
    token = str(data.get("token") or "").strip()
    if not token:
        raise RuntimeError("MES login returned no token")
    with _token_lock:
        _tokens[base] = (token, now + 20 * 3600)
    return token


def _request(method: str, path: str, payload=None):
    last = None
    for base in MES_BASES:
        try:
            token = _login(base)
            return _json_request(base, method, path, payload, token=token)
        except urllib.error.HTTPError as exc:
            # A stale token is retried once through a fresh login.
            if exc.code == 401:
                with _token_lock:
                    _tokens.pop(base, None)
                try:
                    return _json_request(base, method, path, payload, token=_login(base))
                except Exception as retry_exc:
                    last = retry_exc
            else:
                last = exc
        except Exception as exc:
            last = exc
    raise last or RuntimeError("MES unavailable")


def check_sn(sn, station_code):
    code = str(sn or "").strip().upper()
    try:
        result = _request("GET", "/api/station/sn-guard/check/" + urllib.parse.quote(code, safe="") + "?" +
                          urllib.parse.urlencode({"stationCode": station_code}))
        if result.get("duplicate") or result.get("data", {}).get("duplicate"):
            return False, "DUPLICATE_SN_AT_STATION", result
        return True, "CLEAR", result
    except Exception as exc:
        if REQUIRE_SERVICE:
            return False, "SN_SYNC_UNAVAILABLE", {"error": str(exc)}
        return True, "SN_SYNC_OFFLINE_ALLOWED", {"error": str(exc)}


def check_ng(sn):
    code = str(sn or "").strip().upper()
    try:
        # Query the SN-specific MES NG endpoint. The confirmed_ng snapshot is
        # only a cache and can miss a fresh ICT/FCT/ATE defect record.
        result = _request("GET", "/api/mes/ng-check?" + urllib.parse.urlencode({"sn": code}))
        data = result.get("data") if isinstance(result.get("data"), dict) else result
        records = list(data.get("records") or []) if isinstance(data, dict) else []
        if records or bool(data.get("found")):
            return False, "MES_NG", {"found": True, "records": records, "source": "NG_DEFECT_RECORDS"}
        return True, "NO_NG", {"found": False, "records": [], "source": "NG_DEFECT_RECORDS"}
    except Exception as exc:
        if REQUIRE_SERVICE:
            return False, "NG_SYNC_UNAVAILABLE", {"error": str(exc)}
        return True, "NG_SYNC_OFFLINE_ALLOWED", {"error": str(exc)}


def fetch_confirmed_ng(version: int = 0):
    """Fetch the MES confirmed-NG set for silent local SQLite caching."""
    query = urllib.parse.urlencode({"version": max(0, int(version or 0))})
    result = _request("GET", "/api/station/ng-guard?" + query)
    data = result.get("data") if isinstance(result.get("data"), dict) else result
    return {
        "unchanged": bool(data.get("unchanged")),
        "version": int(data.get("version") or 0),
        "items": list(data.get("items") or []),
    }


def register_sn(sn, station_code, source_type="SCANNER"):
    """Complete the local registration after the MES guards pass.

    The common agent persists the accepted scan to its station SQLite.  The
    equipment adapter's normal MES event/outbox performs the authoritative
    production registration, avoiding a second duplicate production event.
    """
    return True, "LOCAL_REGISTERED", {"stationCode": station_code, "sourceType": source_type}


__all__ = ["check_sn", "check_ng", "fetch_confirmed_ng", "register_sn", "PRIMARY", "BACKUP"]

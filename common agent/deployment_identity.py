# -*- coding: utf-8 -*-
"""Local host identity checks for one-package station deployment."""
from __future__ import annotations

import json
import socket
from pathlib import Path


def local_ips():
    values = {"127.0.0.1"}
    try:
        values.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    return values


def _canonical(value: str) -> str:
    value = str(value or "").strip().lower()
    return value[4:] if value.startswith("mod_") else value


def check_station(station_code: str, config_path=None):
    path = Path(config_path or Path(__file__).with_name("deployment_config.json"))
    config = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    ip_map = {str(k): str(v) for k, v in (config.get("ipToStation") or {}).items()}
    host_map = {str(k).lower(): str(v) for k, v in (config.get("hostnameToStation") or {}).items()}
    matches = {ip_map[ip] for ip in local_ips() if ip in ip_map}
    host = socket.gethostname().lower()
    if host in host_map:
        matches.add(host_map[host])
    if not matches:
        return {"status": "UNMAPPED", "stationCode": station_code, "matches": [], "host": host, "ips": sorted(local_ips())}
    ok = any(_canonical(item) == _canonical(station_code) for item in matches)
    return {"status": "MATCH" if ok else "MISMATCH", "stationCode": station_code,
            "matches": sorted(matches), "host": host, "ips": sorted(local_ips())}


__all__ = ["check_station", "local_ips"]

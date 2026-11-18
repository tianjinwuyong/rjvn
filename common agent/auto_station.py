# -*- coding: utf-8 -*-
"""Deploy-one-package station auto configuration.

Priority: explicit STATION_CODE, host/IP deployment map, then safe Gallery
fallback.  Unknown machines are never silently assigned a production station.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAP = ROOT / "station_hosts.json"
DEPLOYMENT_CONFIG = ROOT / "deployment_config.json"


def local_ips():
    values = {"127.0.0.1"}
    try:
        values.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    return values


def detect_station():
    explicit = os.environ.get("STATION_CODE", "").strip()
    if explicit:
        return explicit, "environment"
    data = json.loads(DEPLOYMENT_CONFIG.read_text(encoding="utf-8")) if DEPLOYMENT_CONFIG.exists() else {}
    legacy = json.loads(MAP.read_text(encoding="utf-8")) if MAP.exists() else {}
    ip_map = {str(k): str(v) for k, v in (data.get("ipToStation") or legacy.get("ip") or {}).items()}
    host_map = {str(k).lower(): str(v) for k, v in (data.get("hostnameToStation") or legacy.get("hostname") or {}).items()}
    matches = {ip_map[ip] for ip in local_ips() if ip in ip_map}
    hostname = socket.gethostname().lower()
    if hostname in host_map:
        matches.add(host_map[hostname])
    if len(matches) == 1:
        return next(iter(matches)), "deployment-map"
    return "", "unmapped"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--production", action="store_true")
    args = parser.parse_args()
    station, source = detect_station()
    if not station:
        # Safe fallback: no guessed production station.
        subprocess.call([sys.executable, str(ROOT / "modular_manual_line.py"), "--gallery"])
        return
    env = os.environ.copy()
    env["STATION_CODE"] = station
    env["STATION_CONFIG_SOURCE"] = source
    deployment = json.loads(DEPLOYMENT_CONFIG.read_text(encoding="utf-8"))
    env["STATION_LINE_DOMAIN"] = str(deployment.get("defaultLineDomain", "MANUAL_LINE"))
    command = [sys.executable, str(ROOT / "versions" / "launch_station.py"), "--mode", "mixed", "--station", station]
    if args.production:
        env["STATION_AGENT_PREVIEW"] = "0"
    subprocess.call(command, cwd=str(ROOT), env=env)


if __name__ == "__main__":
    main()

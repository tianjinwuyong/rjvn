# -*- coding: utf-8 -*-
"""Unified Station Agent bootstrap.

One launcher is deployed to every station PC.  The station profile/adapter is
selected from the requested code and the deployment configuration; MES remains
the authority for production decisions.  This module intentionally performs
no route or release mutation by itself.
"""
from __future__ import annotations

import argparse
import json
import threading
import time
import os
import socket
import subprocess
from pathlib import Path

from deployment_config_loader import load_deployment_config, station_config
from deployment_identity import check_station
from station_common_agent import build_common_agent, config_fingerprint

ROOT = Path(__file__).resolve().parent


def start_ui_event_pump(agent):
    """Consume events emitted by extracted station UIs into the agent outbox."""
    event_file = Path(os.environ.get("UNIFIED_UI_EVENT_FILE", Path.home() / ".ruijing_unified_ui_events.jsonl"))

    def pump():
        offset = 0
        while True:
            try:
                if event_file.exists():
                    with event_file.open("r", encoding="utf-8") as stream:
                        stream.seek(offset)
                        for line in stream:
                            offset = stream.tell()
                            item = json.loads(line)
                            agent.queue_event({"source": "abstract-ui", **item})
            except Exception:
                pass
            time.sleep(0.25)

    thread = threading.Thread(target=pump, name="unified-ui-event-pump", daemon=True)
    thread.start()
    return thread


def resolve_station_from_host(config: dict) -> str:
    """Resolve the station from deployment IP/hostname maps only."""
    host = socket.gethostname().lower()
    host_map = {str(k).lower(): str(v) for k, v in (config.get("hostnameToStation") or {}).items()}
    if host in host_map:
        return host_map[host]
    ips = {"127.0.0.1"}
    try:
        ips.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    ip_map = {str(k): str(v) for k, v in (config.get("ipToStation") or {}).items()}
    matches = [ip_map[ip] for ip in ips if ip in ip_map]
    if len(set(matches)) == 1:
        return matches[0]
    if not matches:
        raise RuntimeError(f"No station mapping for host={host}, ips={sorted(ips)}")
    raise RuntimeError(f"Ambiguous station mapping for host={host}, ips={sorted(ips)}: {sorted(set(matches))}")


def legacy_ui_target(canonical: str, config: dict):
    bridge = config.get("legacyUiBridge") or {}
    manifest_path = ROOT / str(bridge.get("manifest", "legacy_ui_manifest.json"))
    if not bridge.get("enabled") or not manifest_path.exists():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    item = (manifest.get("stations") or {}).get(canonical)
    if not item: return None
    root = (ROOT / str(bridge.get("root", ""))).resolve()
    # Production default is the proven 2D station UI/agent.  3D shells are
    # opt-in only and are never started by Unified Station automatically.
    entry = item.get("agent") if str(bridge.get("uiMode", "2D")).upper() == "2D" else (item.get("ui") or item.get("agent"))
    target = root / str(item.get("folder", "")) / str(entry or "")
    if target.exists():
        return target
    # Deployment folders may contain localized names/encoding variants. Find
    # the numbered station folder by its stable prefix, then the entry file.
    import sys
    project_roots = [ROOT.parent]
    if getattr(sys, 'frozen', False):
        project_roots.insert(0, Path(sys.executable).resolve().parent.parent)
    folder_hint = str(item.get("folder", ""))
    number = folder_hint.split(')')[0].lstrip('(') if ')' in folder_hint else ''
    for project_root in project_roots:
      named_root = project_root / '瑞晶越南工位-正式命名'
      candidate_roots = [named_root / '004-手动线 - 副本', named_root]
      for candidate_root in candidate_roots:
        if not candidate_root.exists():
            continue
        for folder in candidate_root.rglob('*'):
            if not folder.is_dir():
                continue
            name = folder.name
            if number and not name.startswith(f'({number})'):
                continue
            candidate = folder / str(entry or '')
            if candidate.exists():
                return candidate
    return None


def launch_legacy_ui(canonical: str, config: dict, profile: dict):
    target = legacy_ui_target(canonical, config)
    if not target:
        return {"launched": False, "reason": "LEGACY_UI_NOT_FOUND"}
    env = os.environ.copy()
    env.update(config.get("legacyUiBridge", {}).get("environment") or {})
    scanner = profile.get("scanner") or {}
    env.update({
        "STATION_CODE": canonical,
        "LINE_DOMAIN": str(profile.get("lineDomain", "MANUAL_LINE")),
        "STATION_SCANNER_PROTOCOL": str(scanner.get("protocol", "KEYBOARD_WEDGE")),
        "STATION_SCANNER_HOST": str(scanner.get("bindAddress", "0.0.0.0")),
        "STATION_SCANNER_PORT": "" if scanner.get("port") is None else str(scanner.get("port")),
    })
    scanner_port = env["STATION_SCANNER_PORT"]
    if scanner_port:
        # Compatibility names for existing adapters.  The value still comes
        # from the Common Agent profile and is not owned by station code.
        env.update({
            "ICT_SCANNER_TCP_PORT": scanner_port,
            "FCT_SCANNER_TCP_PORT": scanner_port,
            "DEPANEL_SCANNER_TCP_PORT": scanner_port,
            "PACKING_SCANNER_TCP_PORT": scanner_port,
            "HIVOLT_SCANNER_TCP_PORT": scanner_port,
        })
    command = [os.environ.get("PYTHON", "python"), str(target)] if target.suffix.lower() == ".py" else [str(target)]
    process = subprocess.Popen(command, cwd=str(target.parent), env=env)
    return {"launched": True, "target": str(target), "pid": process.pid}


def create_unified_station(requested_code: str, *, preview: bool = True):
    import sys
    config_path = ROOT / "deployment_config.json"
    if getattr(sys, "frozen", False):
        external = Path(sys.executable).resolve().parent / "deployment_config.json"
        if external.exists(): config_path = external
    config = load_deployment_config(config_path)
    profile = station_config(requested_code, config)
    canonical = profile["stationCode"]
    identity = check_station(canonical, config_path)
    mes = config.get("mesDomains", {}).get("MES", {})
    agent = build_common_agent(
        canonical,
        line_domain=profile.get("lineDomain", config.get("defaultLineDomain", "MANUAL_LINE")),
        mes_base_url=mes.get("baseUrl", ""),
        config_version=config_fingerprint(config),
        equipment_adapter=profile.get("adapter", "generic"),
        preview=preview,
    )
    return agent, config, profile, identity


def run_station_ui(agent, profile: dict, *, preview: bool = True) -> None:
    """Render the station-specific UI inside the unified Agent process."""
    import tkinter as tk
    from modular_contract import StationViewModel
    from modular_history import StationHistoryLedger
    from modular_manual_line import ModularStationShell
    from station_registry import StationRegistry

    registry = StationRegistry()
    station = registry.get(profile["stationCode"])
    root = tk.Tk()
    ModularStationShell(
        root,
        StationViewModel(station),
        preview=preview,
        locale="zh",
        history_ledger=StationHistoryLedger(),
        common_agent=agent,
    )
    root.mainloop()


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified Station Agent")
    parser.add_argument("station", nargs="?", help="station code or legacy alias; omit for IP auto-detection")
    parser.add_argument("--live", action="store_true", help="start normal agent lifecycle")
    parser.add_argument("--ui", action="store_true", help="open the station-specific unified UI")
    parser.add_argument("--launch-legacy-ui", action="store_true", help="launch the existing station UI/agent")
    args = parser.parse_args()
    import sys
    config_path = ROOT / "deployment_config.json"
    if getattr(sys, "frozen", False):
        external = Path(sys.executable).resolve().parent / "deployment_config.json"
        if external.exists(): config_path = external
    config = load_deployment_config(config_path)
    requested = args.station
    if not requested:
        # Per-station EXEs are built from this same module. Their filename is
        # the station selector, so deployment needs no command-line argument.
        stem = Path(sys.argv[0]).stem.lower()
        if stem.startswith("unified_manu_") or stem.startswith("unified_auto_"):
            requested = stem[len("unified_"):]
    requested = requested or resolve_station_from_host(config)
    agent, config, profile, identity = create_unified_station(requested, preview=not args.live)
    start_ui_event_pump(agent)
    result = {
        "ok": True,
        "requestedStation": args.station,
        "stationCode": profile["stationCode"],
        "stationId": profile.get("stationId"),
        "lineDomain": profile.get("lineDomain"),
        "lineId": profile.get("lineId"),
        "mesDomain": profile.get("mesDomain"),
        "expectedHostIps": profile.get("expectedHostIps", []),
        "host": socket.gethostname(),
        "identity": identity,
        "configVersion": config_fingerprint(config),
        "mesAccess": config.get("mesAccess", {}),
        "communication": config.get("mesCommunication", {}),
        "scanner": profile.get("scanner", {}),
        "health": agent.health(mes_connected=False, scanner_ready=True, equipment_ready=False),
    }
    # Auto-line builds are Unified Agent entry points only.  They do not
    # inherit the manual-line legacy UI bridge by filename.
    auto_legacy = Path(sys.argv[0]).stem.lower().startswith("unified_manu_") and not args.station
    if args.launch_legacy_ui or auto_legacy:
        result["legacyUi"] = launch_legacy_ui(profile["stationCode"], config, profile)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.ui:
        run_station_ui(agent, profile, preview=not args.live)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

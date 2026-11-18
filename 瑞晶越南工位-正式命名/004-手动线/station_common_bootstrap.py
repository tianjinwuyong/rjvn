# -*- coding: utf-8 -*-
"""Manual-line entry point for the shared station agent.

The shared implementation lives beside the auto-line stations.  Keeping this
small adapter in the manual-line root makes Python launches and PyInstaller
launches resolve the same common runtime instead of depending on the caller's
working directory.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

# Manual-line slim builds keep the operator scan/result surface and shared
# backend services, while omitting KPI/manual/maintenance/retest panels.
os.environ.setdefault("STATION_MINIMAL_UI", "1")


_MANUAL_ROOT = Path(__file__).resolve().parent
_COMMON_ROOT = _MANUAL_ROOT.parent / "common"
_AUTO_ROOT = next(
    (path for path in _MANUAL_ROOT.parent.iterdir()
     if path.is_dir() and path.name.startswith("002-")),
    _MANUAL_ROOT.parent / "002-auto",
)
for _path in (_COMMON_ROOT, _AUTO_ROOT, _MANUAL_ROOT):
    if _path.exists() and str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from mes_direct_fallback import install as install_mes_direct_fallback

install_mes_direct_fallback()

from station_common_agent import CommonStationAgent, build_common_agent
from station_runtime_safety import acquire_single_instance


def ensure_station_api_ports() -> None:
    """Best-effort local firewall setup; never blocks station startup."""
    if os.environ.get("STATION_SKIP_FIREWALL_SETUP", "0").strip().lower() in {"1", "true", "yes"}:
        return
    display = "RJ Manual Station Local Info API"
    try:
        probe = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", f"name={display}"],
            capture_output=True, text=True, encoding="mbcs", errors="replace", timeout=5,
        )
        if display.lower() in (probe.stdout or "").lower():
            return
    except Exception:
        return
    script = _MANUAL_ROOT / "open_station_api_ports.py"
    # In a frozen station, sys.executable is the station EXE itself. Running
    # the helper through it relaunches a second copy of the agent, which then
    # trips the common-agent mutex and shows "Agent is already running".
    # Firewall setup is optional; never self-relaunch a frozen station.
    if script.exists() and not getattr(sys, "frozen", False):
        try:
            subprocess.run([sys.executable, str(script)], cwd=str(_MANUAL_ROOT), check=False, timeout=10)
        except Exception:
            pass


def attach_common_agent(station_code: str, entrypoint: str, equipment_adapter: str) -> CommonStationAgent:
    ensure_station_api_ports()
    preview = os.environ.get("STATION_AGENT_PREVIEW", "1").strip().lower() not in {"0", "false", "no"}
    process_lock = acquire_single_instance("COMMON_AGENT_" + station_code.upper())
    allow_duplicate = preview and os.environ.get("STATION_AGENT_ALLOW_PREVIEW_DUPLICATE", "0").strip().lower() in {"1", "true", "yes"}
    if process_lock is None and not allow_duplicate:
        raise RuntimeError(f"{station_code} Agent is already running")
    # PyInstaller sets ``__file__`` inside the temporary _MEI directory.
    # Use the EXE directory so the shared NG cache survives restarts and is
    # the same database used by the station installation.
    station_dir = (Path(sys.executable).resolve().parent
                   if getattr(sys, "frozen", False)
                   else Path(entrypoint).resolve().parent)
    line_domain = os.environ.get("STATION_LINE_DOMAIN", "MANUAL_LINE").strip().upper()
    if line_domain not in {"MANUAL_LINE", "AUTO_LINE"}:
        raise ValueError(f"Unsupported STATION_LINE_DOMAIN: {line_domain}")
    # Older shared-agent builds do not accept ``resource_roots``.  Keep the
    # manual-line launcher compatible with both generations; station startup
    # must not fail before the UI is created just because that optional hint is
    # unavailable in the bundled common agent.
    common_kwargs = dict(
        line_domain=line_domain,
        mes_base_url=os.environ.get("MES_BASE_URL", ""),
        config_version=os.environ.get("STATION_CONFIG_VERSION", "unpublished"),
        equipment_adapter=equipment_adapter,
        preview=preview,
        db_path=station_dir / "data" / "common_agent.sqlite",
    )
    try:
        agent = build_common_agent(
            station_code, resource_roots=(station_dir, _MANUAL_ROOT), **common_kwargs
        )
    except TypeError as exc:
        if "resource_roots" not in str(exc):
            raise
        agent = build_common_agent(station_code, **common_kwargs)
    agent._common_process_lock = process_lock
    threading.Thread(target=agent.initialize_local_resources, name=f"{station_code}-initial-resource-read", daemon=True).start()
    return agent


__all__ = ["attach_common_agent"]

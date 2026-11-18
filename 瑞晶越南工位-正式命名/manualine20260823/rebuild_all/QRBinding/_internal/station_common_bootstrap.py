# -*- coding: utf-8 -*-
"""Common Agent bootstrap shared by every station entrypoint.

This is deliberately a composition hook: equipment cores and UI remain
station-specific, while identity, local outbox, scanner gateway, history and
diagnostic state are created from the same Common Agent implementation.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

from station_common_agent import CommonStationAgent, build_common_agent
from station_runtime_safety import acquire_single_instance

_COMMON_ROOT = Path(__file__).resolve().parent.parent / "common"
if _COMMON_ROOT.exists() and str(_COMMON_ROOT) not in sys.path:
    sys.path.insert(0, str(_COMMON_ROOT))
from mes_direct_fallback import install as install_mes_direct_fallback

install_mes_direct_fallback()


def ensure_station_api_ports() -> None:
    """Ensure MES local-info firewall rules exist before a shared agent starts."""
    if os.environ.get("STATION_SKIP_FIREWALL_SETUP", "0").strip().lower() in {"1", "true", "yes"}:
        return
    display = "RJ Auto Station Local Info API"
    probe = subprocess.run(["netsh", "advfirewall", "firewall", "show", "rule", f"name={display}"],
                           capture_output=True, text=True, encoding="mbcs", errors="replace")
    if display.lower() in (probe.stdout or "").lower():
        return
    script = Path(__file__).resolve().parents[1] / "open_station_api_ports.py"
    # A frozen station's sys.executable is the station EXE, not Python.
    # Calling the helper through it starts a second station process and
    # causes a false "Agent is already running" failure.
    if script.exists() and not getattr(sys, "frozen", False):
        subprocess.run([sys.executable, str(script)], cwd=str(script.parent), check=False)


def attach_common_agent(station_code: str, entrypoint: str, equipment_adapter: str) -> CommonStationAgent:
    """Create the shared station runtime without contacting or writing MES.

    Production MES transport is still owned by the station core until its
    adapter is explicitly switched to the shared transport.  The common
    runtime defaults to preview/outbox-blocked mode so startup cannot create
    production truth accidentally.
    """
    # In a PyInstaller build, ``__file__`` points into the temporary
    # _MEIPASS extraction directory.  Using it for the common SQLite cache
    # makes MES NG synchronization disappear when the EXE restarts.  The
    # permanent station directory is the directory containing the EXE.
    if getattr(sys, "frozen", False):
        station_dir = Path(sys.executable).resolve().parent
    else:
        station_dir = Path(entrypoint).resolve().parent
    ensure_station_api_ports()
    preview = os.environ.get("STATION_AGENT_PREVIEW", "1").strip().lower() not in {"0", "false", "no"}
    # Every entrypoint using the common bootstrap gets a process-wide guard.
    # Station-specific guards may still exist; this guard runs earlier and
    # prevents a second launcher from creating a second Common Agent first.
    process_lock = acquire_single_instance("COMMON_AGENT_" + station_code.upper())
    # Preview/UI smoke tests may intentionally run beside a production agent.
    # Keep the production single-instance guard unchanged; only an explicit
    # preview opt-in may bypass it so a stale/remote station session cannot be
    # mistaken for a second production launch.
    preview_duplicate = preview and os.environ.get("STATION_AGENT_ALLOW_PREVIEW_DUPLICATE", "0").strip().lower() in {"1", "true", "yes"}
    if process_lock is None and not preview_duplicate:
        raise RuntimeError(f"{station_code} Agent is already running")
    # Domain is deployment configuration so this bootstrap remains reusable.
    line_domain = os.environ.get("STATION_LINE_DOMAIN", "AUTO_LINE").strip().upper()
    if line_domain not in {"MANUAL_LINE", "AUTO_LINE"}:
        raise ValueError(f"Unsupported STATION_LINE_DOMAIN: {line_domain}")
    agent = build_common_agent(
        station_code,
        line_domain=line_domain,
        mes_base_url=os.environ.get("MES_BASE_URL", ""),
        config_version=os.environ.get("STATION_CONFIG_VERSION", "unpublished"),
        equipment_adapter=equipment_adapter,
        preview=preview,
        db_path=station_dir / "data" / "common_agent.sqlite",
        resource_roots=(station_dir,),
    )
    # Keep the mutex alive for the lifetime of the returned Agent.
    agent._common_process_lock = process_lock
    threading.Thread(target=agent.initialize_local_resources,
                     name=f"{station_code}-initial-resource-read", daemon=True).start()
    return agent


__all__ = ["attach_common_agent"]

# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "legacy_ui_manifest.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch pure or mixed legacy station UI")
    parser.add_argument("--station", required=True, choices=list(json.loads(MANIFEST.read_text(encoding="utf-8"))["stations"]))
    parser.add_argument("--mode", choices=("pure", "mixed"), default="mixed")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    row = manifest["stations"][args.station]
    source_root = (ROOT / manifest["sourceRoot"]).resolve()
    station_dir = source_root / row["folder"]
    entry = station_dir / row["agent"]
    if not entry.exists():
        raise SystemExit("Missing legacy entry: " + str(entry))
    env = os.environ.copy()
    deployment = json.loads((ROOT / "deployment_config.json").read_text(encoding="utf-8"))
    env.setdefault("STATION_LINE_DOMAIN", str(deployment.get("defaultLineDomain", "MANUAL_LINE")))
    if args.mode == "mixed":
        env["STATION_AGENT_MODE"] = "MIXED"
        env["STATION_COMMON_AGENT_ROOT"] = str(ROOT)
        env["PYTHONPATH"] = os.pathsep.join((str(ROOT), str(station_dir), env.get("PYTHONPATH", "")))
    else:
        env.pop("STATION_AGENT_MODE", None)
        env.pop("STATION_COMMON_AGENT_ROOT", None)
        env["PYTHONPATH"] = os.pathsep.join((str(station_dir), env.get("PYTHONPATH", "")))
    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    return subprocess.Popen([sys.executable, str(entry)], cwd=str(station_dir), env=env, creationflags=flags).pid


if __name__ == "__main__":
    main()

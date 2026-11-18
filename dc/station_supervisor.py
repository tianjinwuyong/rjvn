"""Small, vendor-neutral supervisor for Ruijing Station Agents.

The supervisor owns process lifecycle only.  It never creates MES, SN, NG, or
repair records.  A named Windows mutex provides the single-instance block;
the child Agent remains the authority for station/MES behavior.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import logging
import os
import subprocess
import sys
import time
from collections import deque
from pathlib import Path
from typing import Deque, List, Optional


class SingleInstance:
    def __init__(self, name: str) -> None:
        self.handle = None
        self.name = "Local\\RUIJING_SUPERVISOR_" + name

    def acquire(self) -> bool:
        if os.name != "nt":
            return True
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        self.handle = kernel32.CreateMutexW(None, False, self.name)
        return bool(self.handle) and kernel32.GetLastError() != 183

    def __enter__(self) -> "SingleInstance":
        if not self.acquire():
            raise SystemExit("station supervisor already running")
        return self

    def __exit__(self, *_: object) -> None:
        if self.handle and os.name == "nt":
            ctypes.windll.kernel32.CloseHandle(self.handle)


def build_logger(log_file: Path) -> logging.Logger:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("station-supervisor")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def read_health(path: Optional[Path]) -> dict:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def run_supervisor(args: argparse.Namespace) -> int:
    agent = Path(args.agent).resolve()
    if not agent.is_file():
        raise SystemExit(f"agent executable not found: {agent}")
    workdir = Path(args.working_dir or agent.parent).resolve()
    log_file = Path(args.log_file or (workdir / "supervisor.log"))
    logger = build_logger(log_file)
    mutex_name = args.mutex_name or args.station_code
    health_file = Path(args.health_file) if args.health_file else None

    restart_times: Deque[float] = deque()
    backoff = 2.0
    with SingleInstance(mutex_name):
        logger.info("supervisor started station=%s agent=%s", args.station_code, agent)
        while True:
            now = time.time()
            while restart_times and now - restart_times[0] > args.window_seconds:
                restart_times.popleft()
            if len(restart_times) >= args.max_restarts:
                cooldown = max(5.0, args.window_seconds - (now - restart_times[0]))
                logger.error("restart limit reached; cooldown=%.1fs", cooldown)
                time.sleep(cooldown)
                continue

            command = [str(agent), *args.agent_arg]
            try:
                child = subprocess.Popen(
                    command,
                    cwd=str(workdir),
                    creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
                )
            except OSError:
                logger.exception("agent start failed")
                restart_times.append(time.time())
                time.sleep(backoff)
                backoff = min(args.max_backoff, backoff * 2)
                continue

            logger.info("agent started pid=%s", child.pid)
            code = child.wait()
            if args.once:
                logger.info("agent exited code=%s; once mode complete", code)
                return int(code or 0)
            restart_times.append(time.time())
            logger.warning("agent exited code=%s; restarting after %.1fs", code, backoff)
            if health_file:
                health_file.parent.mkdir(parents=True, exist_ok=True)
                health_file.write_text(json.dumps({"stationCode": args.station_code,
                                                    "status": "restarting",
                                                    "exitCode": code,
                                                    "timestamp": int(time.time() * 1000)}),
                                       encoding="utf-8")
            time.sleep(backoff)
            backoff = min(args.max_backoff, backoff * 2)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ruijing Station Agent process supervisor")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="start and keep one Agent alive")
    run.add_argument("--station-code", required=True)
    run.add_argument("--agent", required=True)
    run.add_argument("--working-dir")
    run.add_argument("--log-file")
    run.add_argument("--health-file")
    run.add_argument("--mutex-name")
    run.add_argument("--max-restarts", type=int, default=5)
    run.add_argument("--window-seconds", type=int, default=600)
    run.add_argument("--max-backoff", type=float, default=60.0)
    run.add_argument("--once", action="store_true", help="test one lifecycle; never restart")
    run.add_argument("agent_arg", nargs=argparse.REMAINDER)
    return parser


if __name__ == "__main__":
    ns = build_parser().parse_args()
    if ns.command == "run":
        raise SystemExit(run_supervisor(ns))

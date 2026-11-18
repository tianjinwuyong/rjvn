"""Read-only MES and station-agent monitoring helpers for Agentic OS."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import socket
import time
import urllib.request

MES_URL = "http://192.168.6.155:8080/"
STATIONS = [
    {"ip": f"192.168.6.{n}", "name": f"Manual station .{n}"}
    for n in range(91, 101)
]
PORTS = {"winrm": 5985, "ssh": 22, "scanner": 1003}


def _probe_port(ip: str, port: int, timeout: float = 0.7) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def _probe_station(station: dict) -> dict:
    ip = station["ip"]
    result = {**station, "ports": {}}
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = {pool.submit(_probe_port, ip, port): name for name, port in PORTS.items()}
        for job in as_completed(jobs):
            result["ports"][jobs[job]] = job.result()
    result["reachable"] = any(result["ports"].values())
    return result


def mes_status() -> dict:
    started = time.perf_counter()
    try:
        request = urllib.request.Request(MES_URL, headers={"User-Agent": "AgenticOS-StationToolbox/1.0"})
        with urllib.request.urlopen(request, timeout=3) as response:
            response.read(128)
            return {
                "url": MES_URL,
                "reachable": True,
                "status": response.status,
                "latency_ms": round((time.perf_counter() - started) * 1000),
            }
    except Exception as exc:
        return {
            "url": MES_URL,
            "reachable": False,
            "status": None,
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "detail": str(exc),
        }


def toolbox_status() -> dict:
    with ThreadPoolExecutor(max_workers=10) as pool:
        stations = list(pool.map(_probe_station, STATIONS))
    return {
        "updated": datetime.now(timezone.utc).isoformat(),
        "mes": mes_status(),
        "stations": stations,
        "ports": PORTS,
    }

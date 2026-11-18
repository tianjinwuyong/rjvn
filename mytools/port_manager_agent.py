# -*- coding: utf-8 -*-
"""
Factory Station Port Manager - Pydantic AI Agent
手动线 (EPS18W) only — 12 stations from dc/stations.xlsx

Usage:
    python port_manager_agent.py
    # Then type commands like:
    #   "scan all stations"
    #   "open port 22 on all stations"
    #   "check station 192.168.6.90"
"""
from __future__ import annotations

import socket
import subprocess
import time
from dataclasses import dataclass
from enum import Enum

import paramiko
from pydantic import BaseModel

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.providers.ollama import OllamaProvider


# =============================================================================
# Station Database — 手动线 (EPS18W) from dc/stations.xlsx
# =============================================================================

STATIONS = [
    {"name": "波峰焊",     "ip": "192.168.1.10",  "user": "ZHX"},
    {"name": "AOI",        "ip": "192.168.6.90",  "user": "aivs"},
    {"name": "ICT",        "ip": "192.168.6.91",  "user": "Admin"},
    {"name": "FCT",        "ip": "192.168.6.92",  "user": "Administrator"},
    {"name": "分板机",      "ip": "192.168.6.93",  "user": "Administrator"},
    {"name": "绑码",       "ip": "192.168.6.94",  "user": "Administrator"},
    {"name": "组装ATE",    "ip": "192.168.6.95",  "user": "Administrator"},
    {"name": "超声波",      "ip": "192.168.6.96",  "user": "PC"},
    {"name": "安托森老化",  "ip": "192.168.6.97",  "user": "Administrator"},
    {"name": "高压测试仪",  "ip": "192.168.6.98",  "user": "Administrator"},
    {"name": "包装ATE",    "ip": "192.168.6.99",  "user": "Administrator"},
    {"name": "包装",       "ip": "192.168.6.100", "user": "Administrator"},
]

# PowerShell script to enable SSH + port 22 on Windows
ENABLE_SSH_SCRIPT = r"""
$ErrorActionPreference = "SilentlyContinue"
$cap = Get-WindowsCapability -Online -Name "OpenSSH.Server*"
if ($cap.State -ne "Installed") {
    Add-WindowsCapability -Online -Name "OpenSSH.Server~~~~0.0.1.0"
}
Start-Service sshd
Set-Service sshd -StartupType Automatic
$rule = Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP"
if ($rule) {
    Enable-NetFirewallRule -Name "OpenSSH-Server-In-TCP"
} else {
    New-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -DisplayName "OpenSSH Server (sshd)" -Direction Inbound -Protocol TCP -LocalPort 22 -Action Allow -Profile Any -Enabled True
}
$r2 = Get-NetFirewallRule -Name "Port22-Open" -ErrorAction SilentlyContinue
if (-not $r2) {
    New-NetFirewallRule -Name "Port22-Open" -DisplayName "Port22-Open" -Direction Inbound -Protocol TCP -LocalPort 22 -Action Allow -Profile Any -Enabled True
}
Write-Output "SUCCESS"
"""


# =============================================================================
# Pydantic Models
# =============================================================================

class StationStatus(str, Enum):
    UNKNOWN = "unknown"
    PORT_OPEN = "port_open"
    PORT_CLOSED = "port_closed"
    SUCCESS = "success"
    FAILED = "failed"
    AUTH_FAILED = "auth_failed"
    TIMEOUT = "timeout"


class StationInfo(BaseModel):
    name: str
    ip: str
    user: str


class StationState(BaseModel):
    station: StationInfo
    port_22_open: bool = False
    status: StationStatus = StationStatus.UNKNOWN
    last_error: str | None = None


class ScanResult(BaseModel):
    total: int
    port_open_count: int
    port_closed_count: int
    stations: list[StationState]


class OpenResult(BaseModel):
    station: StationInfo
    success: bool
    message: str


class BatchOpenResult(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: list[OpenResult]


# =============================================================================
# Dependencies
# =============================================================================

@dataclass
class PortManagerDeps:
    password: str
    timeout: int = 90


# =============================================================================
# Helpers
# =============================================================================

def check_port_22(ip: str, timeout: float = 1.5) -> bool:
    """Check if port 22 is open on a host."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        r = sock.connect_ex((ip, 22))
        sock.close()
        return r == 0
    except Exception:
        return False


def enable_ssh_via_ssh(ip: str, user: str, password: str) -> tuple[bool, str]:
    """SSH into station and enable port 22."""
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(ip, username=user, password=password, timeout=10)
        cmd = f'powershell -NoProfile -Command "{ENABLE_SSH_SCRIPT}"'
        stdin, stdout, stderr = client.exec_command(cmd, timeout=60)
        stdout.channel.recv_exit_status()
        output_text = stdout.read().decode("utf-8", errors="replace")
        error_text = stderr.read().decode("utf-8", errors="replace")
        client.close()
        if "SUCCESS" in output_text:
            return True, "Port 22 enabled via SSH"
        return False, f"Command failed: {output_text[:100]} {error_text[:100]}"
    except paramiko.AuthenticationException:
        return False, "SSH authentication failed - wrong password"
    except paramiko.SSHException as e:
        return False, f"SSH error: {e}"
    except socket.timeout:
        return False, "Connection timeout"
    except Exception as e:
        return False, f"Error: {e}"


def enable_ssh_via_winrm(ip: str, user: str, password: str) -> tuple[bool, str]:
    """Enable SSH via WinRM/PowerShell Remoting."""
    ps_cmd = (
        f"$sec = ConvertTo-SecureString \"{password}\" -AsPlainText -Force; "
        f"$cred = New-Object System.Management.Automation.PSCredential (\"{user}\", $sec); "
        f"try {{ "
        f"  $s = New-PSSession -ComputerName {ip} -Credential $cred -ErrorAction Stop; "
        f"  Invoke-Command -Session $s -ScriptBlock {{ {ENABLE_SSH_SCRIPT} }}; "
        f"  Remove-PSSession $s; "
        f"  Write-Output \"WINRM_OK\" "
        f"}} catch {{ Write-Output \"WINRM_FAIL: $($_.Exception.Message)\" }}"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=90,
        )
        output_text = r.stdout + r.stderr
        if "WINRM_OK" in output_text or "SUCCESS" in output_text:
            return True, "Port 22 enabled via WinRM"
        return False, f"WinRM failed: {output_text[:150]}"
    except subprocess.TimeoutExpired:
        return False, "WinRM timeout"
    except Exception as e:
        return False, f"WinRM error: {e}"


# =============================================================================
# Agent Tools
# =============================================================================

async def scan_all_stations(ctx: RunContext[PortManagerDeps]) -> ScanResult:
    """Scan all 12 手动线 stations to check which have port 22 open."""
    stations_state = []
    port_open_count = 0
    port_closed_count = 0

    for s in STATIONS:
        port_open = check_port_22(s["ip"], timeout=2.0)
        if port_open:
            port_open_count += 1
        else:
            port_closed_count += 1

        stations_state.append(StationState(
            station=StationInfo(name=s["name"], ip=s["ip"], user=s["user"]),
            port_22_open=port_open,
            status=StationStatus.PORT_OPEN if port_open else StationStatus.PORT_CLOSED,
        ))

    return ScanResult(
        total=len(STATIONS),
        port_open_count=port_open_count,
        port_closed_count=port_closed_count,
        stations=stations_state,
    )


async def scan_single_station(ctx: RunContext[PortManagerDeps], ip: str) -> StationState:
    """Scan a single station by IP address to check port 22 status."""
    station_def = next((s for s in STATIONS if s["ip"] == ip), None)
    if not station_def:
        raise ValueError(f"Unknown station IP: {ip}")

    port_open = check_port_22(ip, timeout=2.0)
    return StationState(
        station=StationInfo(name=station_def["name"], ip=ip, user=station_def["user"]),
        port_22_open=port_open,
        status=StationStatus.PORT_OPEN if port_open else StationStatus.PORT_CLOSED,
    )


async def open_port_22_on_all(ctx: RunContext[PortManagerDeps]) -> BatchOpenResult:
    """Open port 22 (SSH) on ALL 12 手动线 stations.

    Uses SSH if port 22 already open, otherwise falls back to WinRM.
    """
    results = []
    succeeded = 0
    failed = 0
    password = ctx.deps.password

    for s in STATIONS:
        ip = s["ip"]
        user = s["user"]
        name = s["name"]

        time.sleep(0.3)

        if check_port_22(ip):
            ok, msg = enable_ssh_via_ssh(ip, user, password)
        else:
            ok, msg = enable_ssh_via_winrm(ip, user, password)

        if ok:
            succeeded += 1
        else:
            failed += 1

        results.append(OpenResult(
            station=StationInfo(name=name, ip=ip, user=user),
            success=ok,
            message=msg,
        ))

    return BatchOpenResult(
        total=len(STATIONS),
        succeeded=succeeded,
        failed=failed,
        results=results,
    )


async def open_port_22_on_station(ctx: RunContext[PortManagerDeps], ip: str) -> OpenResult:
    """Open port 22 (SSH) on a single station by IP."""
    station_def = next((s for s in STATIONS if s["ip"] == ip), None)
    if not station_def:
        raise ValueError(f"Unknown station IP: {ip}")

    password = ctx.deps.password
    name = station_def["name"]
    user = station_def["user"]

    if check_port_22(ip):
        ok, msg = enable_ssh_via_ssh(ip, user, password)
    else:
        ok, msg = enable_ssh_via_winrm(ip, user, password)

    # Confirm
    if ok:
        time.sleep(1)
        if not check_port_22(ip):
            ok = False
            msg = f"{msg} — but port not confirmed open after enable"

    return OpenResult(
        station=StationInfo(name=name, ip=ip, user=user),
        success=ok,
        message=msg,
    )


# =============================================================================
# Agent
# =============================================================================

SYSTEM_PROMPT = """You are the Factory Station Port Manager for 手动线 (EPS18W).

You manage port 22 (SSH) on 12 manual line stations:
- 波峰焊 192.168.1.10
- AOI 192.168.6.90
- ICT 192.168.6.91
- FCT 192.168.6.92
- 分板机 192.168.6.93
- 绑码 192.168.6.94
- 组装ATE 192.168.6.95
- 超声波 192.168.6.96
- 安托森老化 192.168.6.97
- 高压测试仪 192.168.6.98
- 包装ATE 192.168.6.99
- 包装 192.168.6.100

RULES:
- You MUST have the admin password in deps before opening ports
- Scanning does NOT require a password
- Always report results in Chinese
- If a station fails, suggest next steps

Available commands:
- "scan all stations" / "scan all" → scan_all_stations
- "scan station [IP]" → scan_single_station
- "open port 22 on all" / "open all" → open_port_22_on_all
- "open station [IP]" / "open [IP]" → open_port_22_on_station
"""


def create_agent(model_name: str = "qwen3") -> Agent:
    """Create the port manager agent."""
    model = OllamaModel(
        model_name,
        provider=OllamaProvider(base_url="http://localhost:11434/v1"),
    )
    return Agent(
        model,
        system_prompt=SYSTEM_PROMPT,
        deps_type=PortManagerDeps,
        tools=[
            scan_all_stations,
            scan_single_station,
            open_port_22_on_all,
            open_port_22_on_station,
        ],
    )


# =============================================================================
# CLI
# =============================================================================

async def run_interactive():
    print("=" * 60)
    print("Factory Port Manager - 手动线 (EPS18W)")
    print("=" * 60)
    print()
    print("Commands:")
    print("  scan all stations")
    print("  scan station 192.168.6.90")
    print("  open port 22 on all stations")
    print("  open station 192.168.6.90")
    print("  quit / exit")
    print()

    password = input("Enter admin password (for opening ports): ").strip()
    if not password:
        print("No password — can only scan, cannot open ports")
        password = ""

    deps = PortManagerDeps(password=password)
    agent = create_agent("qwen3")  # change to "hy3" if you have Hy3 on Ollama

    print("\nAgent ready. Type your command.\n")

    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        try:
            result = await agent.run(user_input, deps=deps)
            print()
            print(result.output)
            print()
        except Exception as e:
            print(f"\nError: {e}\n")


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_interactive())

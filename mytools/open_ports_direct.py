# -*- coding: utf-8 -*-
"""Direct port 22 opener for 手动线 EPS18W — no AI agent needed."""
import sys, os
sys.path.insert(0, r"C:\Users\tianj\Desktop\越南工厂瑞晶")

import subprocess
import tempfile
import time
import paramiko
from mytools.port_manager_agent import STATIONS, check_port_22, enable_ssh_via_ssh

PASSWORD = "rj"

ENABLE_SCRIPT = r"""
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


def write_script_to_temp() -> str:
    """Write the enable script to a temp .ps1 file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".ps1", prefix="ssh_enable_")
    with os.fdopen(fd, "w", encoding="utf-8-sig") as f:
        f.write(ENABLE_SCRIPT)
    return path


def winrm_basic(ip: str, user: str, password: str, script_path: str) -> tuple[bool, str]:
    """WinRM with Basic auth + local script file - no domain/Kerberos needed."""
    ps = (
        f"$u='{user}';$p=ConvertTo-SecureString '{password}' -AsPlainText -Force;"
        f"$c=New-Object Management.Automation.PSCredential($u,$p);"
        f"try{{"
        f"$s=New-PSSession -ComputerName '{ip}' -Credential $c -Authentication Basic -ErrorAction Stop;"
        f"Invoke-Command -Session $s -FilePath '{script_path}';"
        f"Remove-PSSession $s;"
        f"Write-Output 'WINRM_OK'"
        f"}}catch{{Write-Output ('WINRM_FAIL: '+ $_.Exception.Message)}}"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=90,
        )
        out = r.stdout + r.stderr
        if "WINRM_OK" in out or "SUCCESS" in out:
            return True, "Port 22 enabled via WinRM"
        return False, f"WinRM failed: {out[:200]}"
    except subprocess.TimeoutExpired:
        return False, "WinRM timeout"
    except Exception as e:
        return False, f"WinRM error: {e}"


def main():
    script_path = write_script_to_temp()
    print("Opening port 22 on 手动线 EPS18W")
    print("=" * 50)

    results = []
    for s in STATIONS:
        ip = s["ip"]
        user = s["user"]
        name = s["name"]

        print(f"{name:12s} {ip:15s} ... ", end="", flush=True)
        time.sleep(0.3)

        if check_port_22(ip):
            ok, msg = enable_ssh_via_ssh(ip, user, PASSWORD)
        else:
            ok, msg = winrm_basic(ip, user, PASSWORD, script_path)

        status = "OK" if ok else "FAIL"
        print(f"{status} - {msg}")
        results.append((name, ip, ok, msg))

    try:
        os.unlink(script_path)
    except Exception:
        pass

    print()
    succeeded = sum(1 for r in results if r[2])
    failed = sum(1 for r in results if not r[2])
    print(f"Results: {succeeded} OK, {failed} FAILED")

    print()
    print("Rescanning port 22:")
    print("-" * 40)
    for name, ip, _, _ in results:
        open_ = check_port_22(ip)
        print(f"  {name:12s} {ip:15s} {'OPEN' if open_ else 'CLOSED'}")


if __name__ == "__main__":
    main()

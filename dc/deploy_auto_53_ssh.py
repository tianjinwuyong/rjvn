import getpass
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import paramiko


HOST = "192.168.6.53"
USER = "Administrator"
LOCAL_EXE = Path(r"D:\codex-dist-53\Auto_Depanel_Agent.exe")
REMOTE_DIR = r"D:\stations"
REMOTE_EXE = REMOTE_DIR + r"\Auto_Depanel_Agent.exe"
REMOTE_TEMP = REMOTE_DIR + r"\Auto_Depanel_Agent.exe.uploading"
TASK_NAME = "RuijingAutoDepanel"
REPORT = Path(__file__).with_name("auto-53-deployment-report.json")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def ps_encoded(script):
    return "powershell.exe -NoProfile -NonInteractive -EncodedCommand " + (
        script.encode("utf-16le").hex()
    )


def invoke(client, script):
    # PowerShell -EncodedCommand requires base64, kept local and never includes
    # credentials.
    import base64

    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    command = f"powershell.exe -NoProfile -NonInteractive -EncodedCommand {encoded}"
    _stdin, stdout, stderr = client.exec_command(command, timeout=45)
    out = stdout.read().decode("utf-8", "replace").strip()
    err = stderr.read().decode("utf-8", "replace").strip()
    code = stdout.channel.recv_exit_status()
    if code:
        raise RuntimeError(err or out or f"remote command failed with {code}")
    return out


def main():
    if not LOCAL_EXE.is_file():
        raise FileNotFoundError(LOCAL_EXE)
    local_hash = sha256(LOCAL_EXE)
    password = getpass.getpass(f"Password for {USER}@{HOST}: ")
    result = {
        "ip": HOST,
        "station": "AUTO_DEPANEL",
        "status": "FAILED",
        "phase": "connect",
        "localHash": local_hash,
        "remoteHash": None,
        "backup": None,
        "processPath": None,
        "task": TASK_NAME,
        "tcp1003": False,
        "error": None,
        "checkedAt": datetime.now(timezone.utc).isoformat(),
    }
    client = paramiko.SSHClient()
    transport = None
    try:
        transport = paramiko.Transport((HOST, 22))
        transport.banner_timeout = 10
        transport.auth_timeout = 10
        transport.start_client(timeout=10)

        def interactive_handler(_title, _instructions, prompts):
            return [password if echo is False else "" for _prompt, echo in prompts]

        transport.auth_interactive(USER, interactive_handler)
        client._transport = transport
        password = None
        result["phase"] = "preflight"
        preflight = invoke(
            client,
            r"""
$ErrorActionPreference='Stop'
$api=Test-NetConnection 192.168.6.155 -Port 8080 -InformationLevel Quiet
$web=Test-NetConnection 192.168.6.155 -Port 5178 -InformationLevel Quiet
[pscustomobject]@{DDrive=(Test-Path 'D:\');MesApi=$api;MesWeb=$web} | ConvertTo-Json -Compress
""",
        )
        checks = json.loads(preflight)
        if not checks["DDrive"] or not checks["MesApi"] or not checks["MesWeb"]:
            raise RuntimeError(f"remote preflight failed: {checks}")

        result["phase"] = "backup"
        backup = invoke(
            client,
            rf"""
$ErrorActionPreference='Stop'
New-Item -ItemType Directory -Force '{REMOTE_DIR}' | Out-Null
$target='{REMOTE_EXE}'
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object {{ $_.ExecutablePath -and $_.ExecutablePath.Equals($target,[StringComparison]::OrdinalIgnoreCase) }} |
  ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}
Stop-ScheduledTask -TaskName '{TASK_NAME}' -ErrorAction SilentlyContinue
if(Test-Path -LiteralPath $target){{
  $bak=$target+'.'+(Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')+'.bak'
  Copy-Item -LiteralPath $target -Destination $bak -Force
  $bak
}}
""",
        )
        result["backup"] = backup or None

        result["phase"] = "upload"
        with client.open_sftp() as sftp:
            sftp.put(str(LOCAL_EXE), REMOTE_TEMP)
        invoke(
            client,
            rf"""
$ErrorActionPreference='Stop'
Move-Item -LiteralPath '{REMOTE_TEMP}' -Destination '{REMOTE_EXE}' -Force
$action=New-ScheduledTaskAction -Execute '{REMOTE_EXE}' -WorkingDirectory '{REMOTE_DIR}'
$principal=New-ScheduledTaskPrincipal -UserId "$env:COMPUTERNAME\{USER}" -LogonType Interactive -RunLevel Highest
$settings=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $action -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName '{TASK_NAME}'
""",
        )
        time.sleep(8)

        result["phase"] = "verify"
        verification = json.loads(
            invoke(
                client,
                rf"""
$target='{REMOTE_EXE}'
$p=Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object {{ $_.ExecutablePath -and $_.ExecutablePath.Equals($target,[StringComparison]::OrdinalIgnoreCase) }} |
  Select-Object -First 1
$tcp=[bool](Get-NetTCPConnection -LocalPort 1003 -State Listen -ErrorAction SilentlyContinue)
[pscustomobject]@{{
 Hash=(Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
 ProcessPath=$p.ExecutablePath
 Tcp1003=$tcp
 TaskState=(Get-ScheduledTask -TaskName '{TASK_NAME}').State.ToString()
}} | ConvertTo-Json -Compress
""",
            )
        )
        result["remoteHash"] = verification["Hash"]
        result["processPath"] = verification["ProcessPath"]
        result["tcp1003"] = bool(verification["Tcp1003"])
        result["taskState"] = verification["TaskState"]
        if result["remoteHash"] != local_hash:
            raise RuntimeError("remote hash does not match local EXE")
        if not result["processPath"]:
            raise RuntimeError("remote process is not running")
        if not result["tcp1003"]:
            raise RuntimeError("remote TCP 1003 is not listening")
        result["phase"] = "verified"
        result["status"] = "DEPLOYED"
    except Exception as exc:
        result["error"] = str(exc)
    finally:
        password = None
        client.close()
        if transport is not None:
            transport.close()
        REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    input("Press Enter to close...")
    return 0 if result["status"] == "DEPLOYED" else 1


if __name__ == "__main__":
    sys.exit(main())

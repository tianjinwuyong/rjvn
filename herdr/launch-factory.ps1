<#
.SYNOPSIS
  Launch the RuiJing Vietnam factory development workspace in Herdr.

.DESCRIPTION
  Starts the pieces the factory agents need, then creates one Herdr space
  holding the development panes:

      ┌──────────────────────┬──────────────────────┐
      │ Hermes Agent         │ OpenCode Agent       │
      ├──────────────────────┼──────────────────────┤
      │ Redis 服务           │ rjcli 消息调试        │
      ├──────────────────────┼──────────────────────┤
      │ PostgreSQL 调试      │ 项目文件 / 日志        │
      └──────────────────────┴──────────────────────┘

  Herdr cannot start programs by itself - a layout only references terminal
  addresses that already exist. So this script starts the programs first
  (via hc run / herdr-app do), then switches the window to the factory
  layout.

.PARAMETER NoRedis
  Do not start Redis (if it is already running under another supervisor).

.PARAMETER Layout
  Herdr layout to show. Default: factory

.EXAMPLE
  .\launch-factory.ps1
  .\launch-factory.ps1 -NoRedis
#>

[CmdletBinding()]
param(
  [switch]$NoRedis,
  [string]$Layout = "factory"
)

$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Paths and settings
# ---------------------------------------------------------------------------

$Root       = "C:\Users\tianj\Desktop\越南工厂瑞晶"
$RedisBin   = "C:\Program Files (x86)\HomeNas\2026.8.6.2171\redis\redis-server.exe"
$RedisConf  = "/cygdrive/c/Users/tianj/Desktop/越南工厂瑞晶/herdr/redis-factory.conf"
$Python     = "C:\Users\tianj\AppData\Local\Programs\Python\Python314\python.exe"
$Psql       = "C:\Program Files\PostgreSQL\17\bin\psql.exe"
$Rjcli      = Join-Path $Root "agents\mailbox\rjcli.py"
$HermesMcp  = Join-Path $Root "agents\hermes\redis_mcp.py"

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    OK  $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    !!  $msg" -ForegroundColor Yellow }

function Test-Port($port) {
    try {
        $c = New-Object System.Net.Sockets.TcpClient("127.0.0.1", $port)
        $c.Close()
        return $true
    } catch { return $false }
}

# ---------------------------------------------------------------------------
# 1. Redis
# ---------------------------------------------------------------------------

if (-not $NoRedis) {
    Write-Step "Redis"

    if (Test-Port 6379) {
        Write-Ok "already listening on 127.0.0.1:6379"

    } elseif (Test-Path $RedisBin) {
        # Run Redis as a Herdr terminal that outlives its parent.
        #
        # A plain Start-Process is not enough: the process inherits the
        # console job of the shell that started it, so killing that terminal
        # (or closing it) takes Redis down with it. --outlive-parent detaches
        # it, and --keep means Herdr gives it a fresh shell if the core ever
        # loses it, so the address stays valid.
        $redisConfArg = '"{0}"' -f $RedisConf
        $out = & hc run --bg --name redis-server --cwd "$Root\mailbox" `
                         --outlive-parent --keep -- `
                         ('"{0}"' -f $RedisBin) $redisConfArg 2>&1 | Out-String

        # Verify by port, not by pid. The spawned process exits immediately
        # with "Address already in use" if another instance grabbed the port
        # first, and a pid check would call that a success.
        $up = $false
        foreach ($i in 1..20) {
            Start-Sleep -Milliseconds 500
            if (Test-Port 6379) { $up = $true; break }
        }

        if ($up) {
            Write-Ok "started on 127.0.0.1:6379 (terminal 'redis-server')"
        } else {
            Write-Warn "redis did not accept connections in 10s - see mailbox\redis.log"
            Write-Host "        $($out.Trim())"
        }
    } else {
        Write-Warn "redis-server.exe not found at $RedisBin"
    }
}

# ---------------------------------------------------------------------------
# 2. Postgres check
# ---------------------------------------------------------------------------

Write-Step "PostgreSQL"
if (Test-Port 5432) {
    Write-Ok "listening on 127.0.0.1:5432"
} else {
    Write-Warn "not listening - start the postgresql-x64-17 service"
}

# psql reads the password from .pgpass. On Windows libpq looks in
# %APPDATA%\postgresql\pgpass.conf, not in ~/.pgpass, so make sure the
# Windows location exists too. Without it psql drops to a password prompt
# and the pane looks broken.
$pgpassWin = Join-Path $env:APPDATA "postgresql\pgpass.conf"
if ((Test-Path "C:\Users\tianj\.pgpass") -and -not (Test-Path $pgpassWin)) {
    New-Item -ItemType Directory -Path (Split-Path $pgpassWin) -Force | Out-Null
    Copy-Item "C:\Users\tianj\.pgpass" $pgpassWin -Force
    Write-Ok "pgpass copied to $pgpassWin"
}

# ---------------------------------------------------------------------------
# 3. Mailbox health
# ---------------------------------------------------------------------------

Write-Step "Mailbox"
if (Test-Path $Python) {
    # Quote the path: the project folder has CJK characters and PowerShell
    # would otherwise split it when handing the argument to python.exe.
    & $Python "`"$Rjcli`"" status 2>&1 | Out-String | Write-Host
} else {
    Write-Warn "python not found at $Python"
}

# ---------------------------------------------------------------------------
# 4. Herdr panes
# ---------------------------------------------------------------------------

Write-Step "Herdr panes"

$panes = @(
    @{ name = "hermes";   exe = "hermes";       args = @();                        cwd = $Root },
    @{ name = "opencode"; exe = "opencode";     args = @();                        cwd = "$Root\smt-factory-system" },
    @{ name = "omp";      exe = "omp";          args = @();                        cwd = "$Root\smt-factory-system" },
    @{ name = "redis";    exe = "powershell";   args = @("-NoExit","-Command","Get-Content '$Root\mailbox\redis.log' -Wait -Tail 40"); cwd = "$Root\mailbox" },
    @{ name = "mailbox";  exe = $Python;        args = @($Rjcli, "watch", "3600");   cwd = "$Root\agents\mailbox" },
    @{ name = "psql";     exe = $Psql;          args = @("-h","127.0.0.1","-U","postgres","-d","factory"); cwd = $Root },
    @{ name = "logs";     exe = "powershell";   args = @();                        cwd = "$Root\smt-factory-system" }
)

foreach ($p in $panes) {
    # Quote every argument: the project folder has CJK characters and some
    # arguments contain spaces.
    $argv = @('"{0}"' -f $p.exe) + ($p.args | ForEach-Object { '"{0}"' -f $_ })
    # --outlive-parent so a pane survives the terminal that launched the
    # workspace; --keep so the address stays valid if the program dies.

    # hc writes its errors to stderr. With $ErrorActionPreference = Stop a
    # stderr write aborts the script, so relax it around the call and read
    # the exit code ourselves.
    $errFile = Join-Path $env:TEMP "hc-run-$($p.name).err"
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $out = & hc run --bg --name $p.name --cwd $p.cwd --outlive-parent --keep -- @argv 2>$errFile | Out-String
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    $err = (Get-Content $errFile -Raw -ErrorAction SilentlyContinue)
    Remove-Item $errFile -ErrorAction SilentlyContinue
    $all = "$out$err"

    if ($code -eq 0) {
        Write-Ok "$($p.name) started"
    } elseif ($all -match 'name_taken') {
        # The name is held by a live terminal. Reuse it instead of failing,
        # so the script can be run repeatedly without tearing the workspace
        # down.
        Write-Ok "$($p.name) already running (reused)"
    } else {
        Write-Warn "$($p.name): $($all.Trim())"
    }
}

# ---------------------------------------------------------------------------
# 5. Show the layout
# ---------------------------------------------------------------------------

Write-Step "Layout"
$layoutFile = Join-Path $env:USERPROFILE ".config\herdr-app\layouts\$Layout.json"
if (Test-Path $layoutFile) {
    herdr-app do layout.switch --name $Layout 2>&1 | Out-String | Write-Host
    Write-Ok "switched to '$Layout'"
} else {
    Write-Warn "layout '$Layout' not found at $layoutFile"
    Write-Host "    create it with:"
    Write-Host "      herdr-app do layout.clone '{\"name\":\"main\",\"as\":\"$Layout\"}'"
}

Write-Host ""
Write-Host "Workspace ready." -ForegroundColor Green
Write-Host "  Hermes mailbox MCP : agents\hermes\redis_mcp.py"
Write-Host "  OpenCode mailbox MCP: agents\opencode\redis_mcp.py"
Write-Host "  Mailbox CLI         : python agents\mailbox\rjcli.py status"
Write-Host "  System prompts      : prompts\hermes_system.md, prompts\opencode_system.md"

# RuiJing Vietnam factory — Herdr development workspace

Herdr is the **development workbench** for the RuiJing Vietnam WMS/MES/SMT
system. It is not the production runtime. In the factory the same agents run
as headless background services against the same Redis bus and the same MCP
server code.

```
┌──────────────────────┬──────────────────────┐
│ Hermes Agent         │ OpenCode Agent       │
│ 业务流程 / WMS/MES   │ 代码生成 / SQL / 修复 │
├──────────────────────┼──────────────────────┤
│ Redis 日志           │ 邮箱消息调试 (rjcli)   │
├──────────────────────┼──────────────────────┤
│ PostgreSQL 调试      │ 项目文件 / 日志       │
└──────────────────────┴──────────────────────┘
```

## Start it

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\tianj\Desktop\越南工厂瑞晶\herdr\launch-factory.ps1"
```

The script is idempotent — run it again and it reuses the panes that are
already up.

To reset everything:

```powershell
foreach ($n in @("hermes","opencode","redis","mailbox","psql","logs","redis-server")) { hc kill $n }
```

## Layout

The live layout is `~/.config/herdr-app/layouts/factory.json`.
A copy lives next to this file as `layout-factory.json`; copy it over if the
layout is lost:

```powershell
Copy-Item "C:\Users\tianj\Desktop\越南工厂瑞晶\herdr\layout-factory.json" `
          "$env:USERPROFILE\.config\herdr-app\layouts\factory.json"
herdr-app do layout.switch --name factory
```

`ctrl-shift-l` cycles layouts.

## The message bus

Hermes and OpenCode talk to each other through Redis. They do **not** use
Herdr's agent commands for hand-off.

```
rjvn:mb:<agent>:inbox     LIST    messages waiting for <agent>
rjvn:mb:<agent>:sent      LIST    messages <agent> sent
rjvn:mb:queue             LIST    broadcast queue
rjvn:mb:msg:<id>          STRING  full message JSON (TTL 7 days)
```

Message envelope:

```json
{
  "id": "20261117T014014-282371",
  "from": "hermes",
  "to": "opencode",
  "type": "task | reply | query | result | notice | error",
  "subject": "WMS picking: material issue for WO",
  "body": "...",
  "refs": ["<id>"],
  "meta": {},
  "created": "2026-11-17T01:40:14+00:00"
}
```

### MCP tools (identical for both agents)

| Tool | Purpose |
|---|---|
| `send_message(to, body, type, subject, refs, meta)` | deliver work / an answer |
| `check_inbox(limit, peek, types)` | read this agent's inbox |
| `check_broadcast(limit)` | read the broadcast queue (not consumed) |
| `mailbox_status()` | Redis health, pending counts, known agents |
| `mailbox_peek(agent, limit)` | read another agent's inbox without consuming |
| `mailbox_wait(timeout)` | block until a message arrives |

### Debugging without redis-cli

There is no `redis-cli.exe` in the HomeNas Redis folder. Use `rjcli`:

```powershell
$py = "C:\Users\tianj\AppData\Local\Programs\Python\Python314\python.exe"
$root = "C:\Users\tianj\Desktop\越南工厂瑞晶"

& $py "$root\agents\mailbox\rjcli.py" status
& $py "$root\agents\mailbox\rjcli.py" agents
& $py "$root\agents\mailbox\rjcli.py" inbox opencode
& $py "$root\agents\mailbox\rjcli.py" queue
& $py "$root\agents\mailbox\rjcli.py" get 20261117T014014-282371
& $py "$root\agents\mailbox\rjcli.py" send opencode "hello"
& $py "$root\agents\mailbox\rjcli.py" watch 60
```

## Where things are

| Path | What |
|---|---|
| `agents/mailbox/mailbox.py` | Redis bus, message envelope, key layout |
| `agents/mailbox/mcp_server.py` | shared MCP tool factory |
| `agents/mailbox/rjcli.py` | redis-cli substitute |
| `agents/mailbox/test_mcp.py` | MCP smoke test |
| `agents/hermes/redis_mcp.py` | Hermes entry point (identity `hermes`) |
| `agents/opencode/redis_mcp.py` | OpenCode entry point (identity `opencode`) |
| `agents/omp/redis_mcp.py` | OMP entry point (identity `omp`) |
| `prompts/hermes_system.md` | Hermes system prompt |
| `prompts/opencode_system.md` | OpenCode system prompt |
| `herdr/launch-factory.ps1` | starts everything |
| `herdr/redis-factory.conf` | Redis config |
| `herdr/layout-factory.json` | copy of the live layout |
| `mailbox/` | Redis data dir (dump.rdb, redis.log) |

## MCP registration

**Hermes** — `~/AppData/Local/hermes/config.yaml` (note: *not* `~/.hermes`):

```yaml
mcp_servers:
  factory-mailbox:
    command: C:\Users\tianj\AppData\Local\Programs\Python\Python314\python.exe
    args:
      - C:\Users\tianj\Desktop\越南工厂瑞晶\agents\hermes\redis_mcp.py
    env:
      RJVN_AGENT_NAME: hermes
    enabled: true
```

**OpenCode** — `smt-factory-system/opencode.json`:

```json
"factory-mailbox": {
  "type": "local",
  "command": [
    "C:/Users/tianj/AppData/Local/Programs/Python/Python314/python.exe",
    "C:/Users/tianj/Desktop/越南工厂瑞晶/agents/opencode/redis_mcp.py"
  ],
  "env": { "RJVN_AGENT_NAME": "opencode" },
  "enabled": true
}
```

**OMP** — `~/.hermes/config.yaml` (or via Herdr):

```yaml
mcp_servers:
  omp-mailbox:
    command: C:\Users\tianj\AppData\Local\Programs\Python\Python314\python.exe
    args:
      - C:\Users\tianj\Desktop\越南工厂瑞晶\agents\omp\redis_mcp.py
    env:
      RJVN_AGENT_NAME: omp
    enabled: true
```

## The database

```
PGHOST=127.0.0.1
PGPORT=5432
PGUSER=postgres
PGPASSWORD=postgres
PGDATABASE=factory
PGOPTIONS=-c search_path=rjvn
```

Schema `rjvn` holds 313 tables — the live factory schema.

`psql` is not on PATH: `C:\Program Files\PostgreSQL\17\bin\psql.exe`.

The password lives in `~/.pgpass`. On Windows libpq reads
`%APPDATA%\postgresql\pgpass.conf`, **not** `~/.pgpass` — copy it there or
psql drops to a password prompt.

> The `smt_factory` database also exists but holds only 82 tables and has no
> applied migrations. It is not the live one. Several `.env` files still
> point at it.

## Gotchas found the hard way

1. **The bundled redis-server is a Cygwin build.** Config paths must be
   POSIX (`/cygdrive/c/...`). A Windows path aborts it with
   `Fatal error, can't open config file`.
2. **Two Redis instances race.** The second one exits with
   `bind: Address already in use`. The launch script checks the *port*, not
   the pid, and skips the start when 6379 already answers.
3. **Redis must outlive its parent.** A plain `Start-Process` puts it in the
   launching shell's console job, so killing that terminal kills Redis too.
   The script starts it as a Herdr terminal with `--outlive-parent --keep`.
4. **Windows PowerShell 5.1 reads `.ps1` as ANSI** unless the file has a
   UTF-8 BOM. The project path has CJK characters, so every script here must
   be saved with a BOM or the paths get mangled.
5. **psql needs the password from `pgpass`**, and on Windows that file has to
   be at `%APPDATA%\postgresql\pgpass.conf`.
6. **`hermes mcp add --env` is swallowed into `args`** when it is not the
   last option. Edit the config by hand afterwards.
7. **`hc` writes errors to stderr.** With `$ErrorActionPreference = "Stop"`
   that aborts a script; relax it around the call.

## Tests

```powershell
& "C:\Users\tianj\AppData\Local\Programs\Python\Python314\python.exe" `
  "C:\Users\tianj\Desktop\越南工厂瑞晶\agents\mailbox\test_mcp.py"
```

Expected:

```
[hermes] server: ruijing-factory-mailbox v1.0.0
[hermes] tools: check_broadcast, check_inbox, mailbox_peek, mailbox_status, mailbox_wait, send_message
...
ALL MCP SMOKE TESTS PASSED
```

## Production (Vietnam factory)

Nothing here depends on Herdr. In the factory:

- run the agents as background services (`systemd` / NSSM / a container)
- point `RJVN_REDIS_HOST` / `RJVN_REDIS_PORT` / `RJVN_REDIS_PASSWORD` at the
  factory Redis
- set `RJVN_AGENT_NAME` per service (`hermes`, `opencode`, ...)
- load the same `prompts/*.md`

The MCP server is a stdio process; wrap it in whatever supervises your
services. The message protocol does not change.

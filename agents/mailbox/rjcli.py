#!/usr/bin/env python
"""
rjcli - a small redis-cli substitute for the RuiJing factory workspace.

The bundled redis-server (HomeNas build) ships without redis-cli.exe, so
this stands in for the "redis-cli message debug" pane.

Usage:
  rjcli.py ping
  rjcli.py status                     # server info + mailbox overview
  rjcli.py agents                     # known agents and pending counts
  rjcli.py inbox [agent]              # peek an inbox (default: self)
  rjcli.py queue                      # broadcast queue
  rjcli.py get <message-id>           # one message
  rjcli.py send <to> <body>           # send a message
  rjcli.py watch [seconds]            # tail the broadcast queue
  rjcli.py --host H --port P ...      # override connection settings
"""

from __future__ import annotations

import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_MAILBOX = os.path.join(os.path.dirname(_HERE), "mailbox")
if _MAILBOX not in sys.path:
    sys.path.insert(0, _MAILBOX)

from mailbox import Mailbox, MailboxError  # noqa: E402

SELF = os.environ.get("RJVN_AGENT_NAME", "rjvn-dev")


def out(obj) -> None:
    import json

    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def main(argv: list[str]) -> int:
    host = os.environ.get("RJVN_REDIS_HOST", "127.0.0.1")
    port = int(os.environ.get("RJVN_REDIS_PORT", "6379"))

    args = argv[1:]
    # global overrides: --host H --port P
    cleaned: list[str] = []
    i = 0
    while i < len(args):
        if args[i] == "--host" and i + 1 < len(args):
            host = args[i + 1]
            i += 2
            continue
        if args[i] == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
            i += 2
            continue
        cleaned.append(args[i])
        i += 1
    args = cleaned

    if not args:
        print(__doc__)
        return 0

    cmd = args[0]
    mb = Mailbox(SELF, host=host, port=port)

    try:
        if cmd == "ping":
            out({"ok": mb.ping(), "host": host, "port": port})
        elif cmd == "status":
            info = mb.server_info()
            info["ok"] = True
            info["agents"] = mb.agents()
            info["pending_self"] = mb.pending()
            out(info)
        elif cmd == "agents":
            out({"agents": mb.agents()})
        elif cmd == "inbox":
            agent = args[1] if len(args) > 1 else SELF
            if agent == SELF:
                msgs = mb.check_inbox(peek=True)
            else:
                other = Mailbox(agent, host=host, port=port)
                raw = other._redis.lrange(other._inbox_key(), 0, 49)
                msgs = other._load(raw)
                other.close()
            out({"agent": agent, "count": len(msgs),
                 "messages": [m.to_dict() for m in msgs]})
        elif cmd == "queue":
            msgs = mb.check_broadcast(limit=50)
            out({"count": len(msgs), "messages": [m.to_dict() for m in msgs]})
        elif cmd == "get":
            if len(args) < 2:
                print("usage: rjcli.py get <message-id>", file=sys.stderr)
                return 2
            msg = mb.get_message(args[1])
            out({"found": msg is not None,
                 "message": msg.to_dict() if msg else None})
        elif cmd == "send":
            if len(args) < 3:
                print("usage: rjcli.py send <to> <body>", file=sys.stderr)
                return 2
            msg = mb.send(to=args[1], body=" ".join(args[2:]), type="notice")
            out({"ok": True, "id": msg.id, "summary": msg.summary()})
        elif cmd == "watch":
            seconds = float(args[1]) if len(args) > 1 else 30.0
            print(f"watching broadcast queue for {seconds}s (ctrl-c to stop)")
            deadline = time.time() + seconds
            seen = set()
            warned = False
            while time.time() < deadline:
                try:
                    for m in mb.check_broadcast(limit=50):
                        if m.id not in seen:
                            seen.add(m.id)
                            print(m.summary())
                    warned = False
                except MailboxError as exc:
                    # Redis bounced or was not up yet. Keep the pane alive and
                    # retry, rather than exiting and taking the pane down.
                    if not warned:
                        print(f"[redis unavailable: {exc}] retrying...",
                              file=sys.stderr)
                        warned = True
                time.sleep(1.0)
            out({"watched": seconds, "new_messages": len(seen)})
        else:
            print(f"unknown command {cmd!r}; see the module docstring",
                  file=sys.stderr)
            return 2
    except MailboxError as exc:
        out({"ok": False, "error": str(exc)})
        return 1
    finally:
        mb.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

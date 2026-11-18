#!/usr/bin/env python
"""
RuiJing Vietnam factory - Hermes mailbox MCP server.

Exposes the Redis mailbox tools to the Hermes agent:
  send_message, check_inbox, check_broadcast, mailbox_status,
  mailbox_peek, mailbox_wait

Registered in ~/.hermes/config.yaml under mcp_servers.factory-mailbox.
The same code path runs in the factory as a headless background service:
only the agent identity changes (RJVN_AGENT_NAME).
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_MAILBOX = os.path.join(os.path.dirname(_HERE), "mailbox")
if _MAILBOX not in sys.path:
    sys.path.insert(0, _MAILBOX)

from mcp_server import build_server  # noqa: E402

AGENT = os.environ.get("RJVN_AGENT_NAME", "hermes")


def main() -> None:
    server = build_server(AGENT)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()

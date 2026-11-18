#!/usr/bin/env python
"""
Smoke test for the factory mailbox MCP servers.

Runs the server as a subprocess over stdio, speaks MCP to it, and checks
that the tools are registered and that a message round-trips through Redis.

Usage:  python agents/mailbox/test_mcp.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

PYTHON = sys.executable
SERVERS = {
    "hermes": os.path.join(_ROOT, "agents", "hermes", "redis_mcp.py"),
    "opencode": os.path.join(_ROOT, "agents", "opencode", "redis_mcp.py"),
}


async def probe(agent: str, script: str) -> int:
    params = StdioServerParameters(
        command=PYTHON,
        args=[SCRIPTS[agent]],
        env={**os.environ, "RJVN_AGENT_NAME": agent},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            info = getattr(init, "server_info", None) or getattr(init, "serverInfo", None)
            print(f"[{agent}] server: {info.name} v{info.version}")

            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            print(f"[{agent}] tools: {', '.join(names)}")

            for required in ("send_message", "check_inbox", "mailbox_status"):
                assert required in names, f"{agent}: missing {required}"

            result = await session.call_tool("mailbox_status", {})
            payload = json.loads(result.content[0].text)
            assert payload.get("ok"), f"{agent}: mailbox_status failed: {payload}"
            print(f"[{agent}] redis: v{payload['redis_version']} agents={payload['agents']}")

            sent = await session.call_tool(
                "send_message",
                {"to": "peer", "body": f"mcp smoke test from {agent}",
                 "type": "notice", "subject": "smoke"},
            )
            sent_payload = json.loads(sent.content[0].text)
            assert sent_payload.get("ok"), f"{agent}: send failed: {sent_payload}"
            msg_id = sent_payload["id"]
            print(f"[{agent}] sent {msg_id}")

            got = await session.call_tool("check_inbox", {"limit": 5})
            got_payload = json.loads(got.content[0].text)
            assert got_payload.get("ok"), f"{agent}: check_inbox failed: {got_payload}"
            print(f"[{agent}] inbox count={got_payload['count']}")

    print(f"[{agent}] OK\n")
    return 0


SCRIPTS = SERVERS


async def main() -> int:
    for agent in ("hermes", "opencode"):
        await probe(agent, SERVERS[agent])
    print("ALL MCP SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

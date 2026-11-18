"""
Shared MCP server factory for RuiJing Vietnam factory agents.

Builds the same tool surface (send_message / check_inbox / ...) for any
agent identity. The Hermes and OpenCode entry points differ only in the
agent name they pass in and in how they are launched.

The tool names and behaviour are identical in development (Herdr) and in
the factory (headless background service), so the message protocol does
not drift between the two environments.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from mcp.server.mcpserver import MCPServer

try:
    from .mailbox import Mailbox, MailboxError, Message
except ImportError:  # running as a plain script, not a package
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from mailbox import Mailbox, MailboxError, Message  # type: ignore


PROJECT_ROOT = os.environ.get(
    "RJVN_PROJECT_ROOT", r"C:\Users\tianj\Desktop\越南工厂瑞晶"
)


def build_server(agent: str) -> MCPServer:
    """Create the MCP server exposing the mailbox tools for `agent`."""
    server = MCPServer(
        name="ruijing-factory-mailbox",
        version="1.0.0",
        instructions=(
            f"You are the '{agent}' agent for the RuiJing Vietnam factory "
            "WMS/MES/SMT system. Use send_message and check_inbox to talk to "
            "the other agents. Never use Herdr agent commands for task handoff. "
            f"All project files live under {PROJECT_ROOT}."
        ),
    )

    mailbox = Mailbox(agent)

    # -- tools -----------------------------------------------------------

    @server.tool()
    def send_message(
        to: str,
        body: str,
        type: str = "notice",
        subject: str = "",
        refs: list[str] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> str:
        """
        Send a message to another factory agent via the Redis mailbox.

        Args:
            to: recipient agent name, or "*" to broadcast to everyone.
            body: the message text.
            type: one of task, reply, query, result, notice, error.
            subject: short subject line.
            refs: ids of messages this one replies to.
            meta: extra key/value data for the recipient.
        """
        try:
            msg = mailbox.send(
                to=to,
                body=body,
                type=type,
                subject=subject,
                refs=refs,
                meta=meta,
            )
            return json.dumps(
                {"ok": True, "id": msg.id, "to": msg.recipient,
                 "summary": msg.summary()},
                ensure_ascii=False,
            )
        except MailboxError as exc:
            return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)

    @server.tool()
    def check_inbox(
        limit: int = 10, peek: bool = False, types: list[str] | None = None
    ) -> str:
        """
        Read messages waiting in this agent's inbox.

        Args:
            limit: max messages to return (1-100).
            peek: if true, leave messages in the inbox instead of consuming.
            types: only return these message types.
        """
        try:
            messages = mailbox.check_inbox(limit=limit, peek=peek, types=types)
            return json.dumps(
                {
                    "ok": True,
                    "count": len(messages),
                    "messages": [m.to_dict() for m in messages],
                },
                ensure_ascii=False,
            )
        except MailboxError as exc:
            return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)

    @server.tool()
    def check_broadcast(limit: int = 10) -> str:
        """Read the broadcast queue without consuming it."""
        try:
            messages = mailbox.check_broadcast(limit=limit)
            return json.dumps(
                {
                    "ok": True,
                    "count": len(messages),
                    "messages": [m.to_dict() for m in messages],
                },
                ensure_ascii=False,
            )
        except MailboxError as exc:
            return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)

    @server.tool()
    def mailbox_status() -> str:
        """Report Redis connectivity, pending counts and known agents."""
        try:
            info = mailbox.server_info()
            info["ok"] = True
            info["self"] = agent
            info["pending"] = mailbox.pending()
            info["agents"] = mailbox.agents()
            return json.dumps(info, ensure_ascii=False, default=str)
        except MailboxError as exc:
            return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)

    @server.tool()
    def mailbox_peek(agent: str, limit: int = 10) -> str:
        """
        Inspect another agent's inbox without consuming it.

        Useful for supervisors and for debugging the message flow.
        """
        try:
            other = Mailbox(agent)
            try:
                raw = other._redis.lrange(other._inbox_key(), 0, max(0, int(limit) - 1))
                msgs = other._load(raw)
            finally:
                other.close()
            return json.dumps(
                {"ok": True, "agent": agent, "count": len(msgs),
                 "messages": [m.to_dict() for m in msgs]},
                ensure_ascii=False,
            )
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)

    @server.tool()
    def mailbox_wait(timeout: float = 30.0) -> str:
        """Block until a message arrives (or the timeout expires)."""
        try:
            messages = mailbox.wait_for_mail(timeout=timeout)
            return json.dumps(
                {"ok": True, "count": len(messages),
                 "messages": [m.to_dict() for m in messages]},
                ensure_ascii=False,
            )
        except MailboxError as exc:
            return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)

    return server


def main(agent: str) -> None:
    server = build_server(agent)
    server.run(transport="stdio")


if __name__ == "__main__":
    # Each entry point sets its own identity before calling main().
    raise SystemExit("use agents/hermes/redis_mcp.py or agents/opencode/redis_mcp.py")

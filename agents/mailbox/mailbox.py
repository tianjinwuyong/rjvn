"""
Redis mailbox core for RuiJing Vietnam factory agents.

Shared by the Hermes and OpenCode MCP servers. The message envelope, the
Redis key layout and the queue semantics live here so both agents speak the
exact same protocol. Dev (Herdr) and factory (headless service) run the same
code against the same Redis instance.

Redis key layout
----------------
  rjvn:mb:<agent>:<inbox>     LIST    messages waiting for <agent>
  rjvn:mb:<agent>:sent        LIST    messages <agent> sent (audit trail)
  rjvn:mb:queue               LIST    global broadcast queue
  rjvn:mb:msg:<id>            STRING  full message JSON (TTL 7 days)

Message envelope (JSON)
-----------------------
  {
    "id":       "20261117T091500-ab12cd",
    "from":     "hermes",
    "to":       "opencode",           # or "*" for broadcast
    "type":     "task" | "reply" | "query" | "result" | "notice",
    "subject":  "short subject",
    "body":     "message body",
    "refs":     ["<id>", ...],        # reply-to chain
    "meta":     { ... },              # free-form
    "created":  "2026-11-17T09:15:00Z"
  }
"""

from __future__ import annotations

import json
import os
import socket
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

import redis

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

NAMESPACE = os.environ.get("RJVN_MAILBOX_NS", "rjvn:mb")
REDIS_HOST = os.environ.get("RJVN_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("RJVN_REDIS_PORT", "6379"))
REDIS_DB = int(os.environ.get("RJVN_REDIS_DB", "0"))
REDIS_PASSWORD = os.environ.get("RJVN_REDIS_PASSWORD") or None
REDIS_SOCKET_TIMEOUT = float(os.environ.get("RJVN_REDIS_TIMEOUT", "10"))

MESSAGE_TTL_SECONDS = int(os.environ.get("RJVN_MAILBOX_TTL", str(7 * 24 * 3600)))
MAX_INBOX = int(os.environ.get("RJVN_MAILBOX_MAX", "500"))

VALID_TYPES = ("task", "reply", "query", "result", "notice", "error")


class MailboxError(RuntimeError):
    """Raised when the mailbox cannot complete an operation."""


# --------------------------------------------------------------------------
# Message envelope
# --------------------------------------------------------------------------


@dataclass
class Message:
    sender: str
    recipient: str
    type: str = "notice"
    subject: str = ""
    body: str = ""
    refs: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    id: str = ""
    created: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = _new_id()
        if not self.created:
            self.created = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if self.type not in VALID_TYPES:
            raise MailboxError(
                f"invalid message type {self.type!r}; expected one of {VALID_TYPES}"
            )
        if not self.sender:
            raise MailboxError("message needs a sender")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Message":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in raw.items() if k in known})

    def summary(self) -> str:
        body = (self.body or "").strip().replace("\n", " ")
        if len(body) > 160:
            body = body[:157] + "..."
        return f"[{self.id}] {self.sender}->{self.recipient} ({self.type}) {self.subject}: {body}"


def _new_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{stamp}-{uuid.uuid4().hex[:6]}"


# --------------------------------------------------------------------------
# Mailbox
# --------------------------------------------------------------------------


class Mailbox:
    """Redis-backed agent mailbox."""

    def __init__(
        self,
        agent: str,
        host: str = REDIS_HOST,
        port: int = REDIS_PORT,
        db: int = REDIS_DB,
        password: str | None = REDIS_PASSWORD,
    ) -> None:
        self.agent = agent
        self.host = host
        self.port = port
        try:
            self._redis = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                socket_timeout=REDIS_SOCKET_TIMEOUT,
                socket_connect_timeout=REDIS_SOCKET_TIMEOUT,
                decode_responses=True,
            )
        except Exception as exc:  # pragma: no cover - config error
            raise MailboxError(f"cannot create redis client: {exc}") from exc

    # -- keys ------------------------------------------------------------

    def _inbox_key(self, agent: str | None = None) -> str:
        return f"{NAMESPACE}:{agent or self.agent}:inbox"

    def _sent_key(self, agent: str | None = None) -> str:
        return f"{NAMESPACE}:{agent or self.agent}:sent"

    @property
    def _queue_key(self) -> str:
        return f"{NAMESPACE}:queue"

    def _msg_key(self, msg_id: str) -> str:
        return f"{NAMESPACE}:msg:{msg_id}"

    # -- health ----------------------------------------------------------

    def ping(self) -> bool:
        try:
            return bool(self._redis.ping())
        except redis.RedisError:
            return False

    def server_info(self) -> dict[str, Any]:
        try:
            info = self._redis.info()
            return {
                "host": self.host,
                "port": self.port,
                "redis_version": info.get("redis_version"),
                "uptime_seconds": info.get("uptime_in_seconds"),
                "connected_clients": info.get("connected_clients"),
                "namespace": NAMESPACE,
            }
        except redis.RedisError as exc:
            raise MailboxError(f"redis unavailable at {self.host}:{self.port}: {exc}") from exc

    # -- send ------------------------------------------------------------

    def send(
        self,
        to: str,
        body: str = "",
        type: str = "notice",
        subject: str = "",
        refs: list[str] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> Message:
        """Deliver a message to another agent (or "*" for broadcast)."""
        msg = Message(
            sender=self.agent,
            recipient=to,
            type=type,
            subject=subject,
            body=body,
            refs=list(refs or []),
            meta=dict(meta or {}),
        )
        payload = json.dumps(msg.to_dict(), ensure_ascii=False)

        try:
            pipe = self._redis.pipeline()
            pipe.setex(self._msg_key(msg.id), MESSAGE_TTL_SECONDS, payload)
            if to == "*":
                pipe.lpush(self._queue_key, msg.id)
                pipe.ltrim(self._queue_key, 0, MAX_INBOX - 1)
            else:
                pipe.lpush(self._inbox_key(to), msg.id)
                pipe.ltrim(self._inbox_key(to), 0, MAX_INBOX - 1)
            pipe.lpush(self._sent_key(), msg.id)
            pipe.ltrim(self._sent_key(), 0, MAX_INBOX - 1)
            pipe.execute()
        except redis.RedisError as exc:
            raise MailboxError(f"send failed: {exc}") from exc

        return msg

    # -- receive ---------------------------------------------------------

    def check_inbox(
        self,
        limit: int = 10,
        peek: bool = False,
        types: list[str] | None = None,
    ) -> list[Message]:
        """
        Read messages addressed to this agent.

        peek=False (default) removes them from the inbox, so a message is
        handled once. peek=True leaves them in place for inspection.
        """
        limit = max(1, min(int(limit), 100))
        key = self._inbox_key()
        try:
            raw_ids = self._redis.lrange(key, 0, limit - 1)
            if not raw_ids:
                return []
            messages = self._load(raw_ids)
            if types:
                wanted = set(types)
                messages = [m for m in messages if m.type in wanted]
            if not peek and messages:
                taken = {m.id for m in messages}
                self._redis.lrem(key, 0, *[i for i in raw_ids if i in taken])
            return messages
        except redis.RedisError as exc:
            raise MailboxError(f"check_inbox failed: {exc}") from exc

    def check_broadcast(self, limit: int = 10) -> list[Message]:
        """Read the broadcast queue without consuming it."""
        try:
            raw_ids = self._redis.lrange(self._queue_key, 0, max(0, int(limit) - 1))
            return self._load(raw_ids)
        except redis.RedisError as exc:
            raise MailboxError(f"check_broadcast failed: {exc}") from exc

    def _load(self, raw_ids: list[str]) -> list[Message]:
        if not raw_ids:
            return []
        payloads = self._redis.mget([self._msg_key(i) for i in raw_ids])
        out: list[Message] = []
        for msg_id, payload in zip(raw_ids, payloads):
            if not payload:
                continue
            try:
                out.append(Message.from_dict(json.loads(payload)))
            except (json.JSONDecodeError, TypeError):
                continue
        return out

    # -- inspection ------------------------------------------------------

    def pending(self, agent: str | None = None) -> int:
        try:
            return int(self._redis.llen(self._inbox_key(agent)))
        except redis.RedisError:
            return 0

    def sent(self, limit: int = 20) -> list[Message]:
        try:
            raw_ids = self._redis.lrange(self._sent_key(), 0, max(0, int(limit) - 1))
            return self._load(raw_ids)
        except redis.RedisError as exc:
            raise MailboxError(f"sent failed: {exc}") from exc

    def get_message(self, msg_id: str) -> Message | None:
        try:
            payload = self._redis.get(self._msg_key(msg_id))
        except redis.RedisError:
            return None
        if not payload:
            return None
        try:
            return Message.from_dict(json.loads(payload))
        except (json.JSONDecodeError, TypeError):
            return None

    def agents(self) -> list[dict[str, Any]]:
        """List known agents and their pending counts."""
        out: list[dict[str, Any]] = []
        try:
            prefix = f"{NAMESPACE}:"
            for key in self._redis.scan_iter(match=f"{prefix}*:inbox"):
                # key looks like rjvn:mb:<agent>:inbox
                rest = key[len(prefix):]
                agent = rest[: -len(":inbox")] if rest.endswith(":inbox") else rest
                if not agent:
                    continue
                out.append({"agent": agent, "pending": self.pending(agent)})
        except redis.RedisError:
            pass
        return sorted(out, key=lambda a: a["agent"])

    # -- helpers ---------------------------------------------------------

    def wait_for_mail(
        self,
        timeout: float = 30.0,
        poll: float = 1.0,
    ) -> list[Message]:
        """Block until a message arrives or the timeout expires."""
        deadline = time.time() + max(1.0, float(timeout))
        while time.time() < deadline:
            messages = self.check_inbox(peek=True)
            if messages:
                # consume what we saw
                return self.check_inbox(peek=False)
            time.sleep(max(0.1, float(poll)))
        return []

    def close(self) -> None:
        try:
            self._redis.close()
        except Exception:
            pass


def local_identity() -> str:
    """Best-effort identity for a machine running the factory agents."""
    return socket.gethostname()

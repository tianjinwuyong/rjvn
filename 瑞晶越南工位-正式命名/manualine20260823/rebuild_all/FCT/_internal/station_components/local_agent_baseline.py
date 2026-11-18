# -*- coding: utf-8 -*-
"""Common local-agent baseline for Manual and Auto station agents.

The component is local-first: it records evidence in SQLite, never approves
MES decisions, and keeps an auditable trail for operator/maintenance use.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import shutil
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Mapping, Optional


ROLES = {"OPERATOR", "MAINTENANCE", "QUALITY", "SUPERVISOR", "ADMIN"}
ROLE_PERMISSIONS = {
    "OPERATOR": {"SCAN", "DAILY_CHECK", "OPERATION_REPORT", "VIEW_SOP"},
    "MAINTENANCE": {"SCAN", "DAILY_CHECK", "OPERATION_REPORT", "VIEW_SOP", "MAINTENANCE", "DIAGNOSTICS"},
    "QUALITY": {"SCAN", "DAILY_CHECK", "OPERATION_REPORT", "VIEW_SOP", "NG_REVIEW", "RETEST_REQUEST"},
    "SUPERVISOR": {"SCAN", "DAILY_CHECK", "OPERATION_REPORT", "VIEW_SOP", "NG_REVIEW", "RETEST_REQUEST", "RELEASE_REVIEW"},
    "ADMIN": {"*"},
}


class LocalAgentBaseline:
    """Shared local controls used by every station domain."""

    def __init__(self, db_path: str | Path, station_code: str, line_domain: str):
        self.db_path = Path(db_path)
        self.station_code = str(station_code)
        self.line_domain = str(line_domain)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS agent_users (
              user_id TEXT PRIMARY KEY, role TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
              updated_at INTEGER NOT NULL, password_salt TEXT NOT NULL DEFAULT '',
              password_hash TEXT NOT NULL DEFAULT '', failed_attempts INTEGER NOT NULL DEFAULT 0,
              locked_until INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS agent_audit (
              audit_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, role TEXT NOT NULL,
              action TEXT NOT NULL, result TEXT NOT NULL, details TEXT NOT NULL,
              created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS agent_health (
              health_id TEXT PRIMARY KEY, status TEXT NOT NULL, payload TEXT NOT NULL,
              created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS document_acknowledgments (
              acknowledgment_id TEXT PRIMARY KEY, document_id TEXT NOT NULL, language TEXT NOT NULL,
              version TEXT NOT NULL, user_id TEXT NOT NULL, created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS agent_config_versions (
              version_id TEXT PRIMARY KEY, config_name TEXT NOT NULL, version TEXT NOT NULL,
              payload TEXT NOT NULL, sha256 TEXT NOT NULL, created_at INTEGER NOT NULL,
              active INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS agent_alarms (
              alarm_id TEXT PRIMARY KEY, severity TEXT NOT NULL, code TEXT NOT NULL,
              message TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'OPEN',
              created_at INTEGER NOT NULL, acknowledged_by TEXT NOT NULL DEFAULT '', acknowledged_at INTEGER
            );
            CREATE TABLE IF NOT EXISTS mes_event_outbox (
              event_id TEXT PRIMARY KEY, endpoint TEXT NOT NULL, payload TEXT NOT NULL,
              created_at INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
              status TEXT NOT NULL DEFAULT 'PENDING', last_error TEXT NOT NULL DEFAULT '', sent_at INTEGER
            );
            """)
            columns = {row[1] for row in db.execute("PRAGMA table_info(agent_users)")}
            for name, definition in (("password_salt", "TEXT NOT NULL DEFAULT ''"), ("password_hash", "TEXT NOT NULL DEFAULT ''"), ("failed_attempts", "INTEGER NOT NULL DEFAULT 0"), ("locked_until", "INTEGER NOT NULL DEFAULT 0")):
                if name not in columns:
                    db.execute(f"ALTER TABLE agent_users ADD COLUMN {name} {definition}")

    def set_user(self, user_id: str, role: str, password: str, *, active: bool = True) -> None:
        role = str(role).upper()
        if role not in ROLES or len(password) < 8:
            raise ValueError("role must be valid and password must contain at least 8 characters")
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000).hex()
        with sqlite3.connect(self.db_path) as db:
            db.execute("INSERT INTO agent_users(user_id,role,active,updated_at,password_salt,password_hash,failed_attempts,locked_until) VALUES(?,?,?,?,?,?,0,0) ON CONFLICT(user_id) DO UPDATE SET role=excluded.role,active=excluded.active,updated_at=excluded.updated_at,password_salt=excluded.password_salt,password_hash=excluded.password_hash,failed_attempts=0,locked_until=0",
                       (str(user_id), role, int(active), int(time.time() * 1000), salt.hex(), digest))

    def authenticate(self, user_id: str, password: str) -> Optional[str]:
        now = int(time.time() * 1000)
        audit_role = "UNKNOWN"
        success = False
        with sqlite3.connect(self.db_path) as db:
            row = db.execute("SELECT role,active,password_salt,password_hash,failed_attempts,locked_until FROM agent_users WHERE user_id=?", (str(user_id),)).fetchone()
            if not row or not row[1] or int(row[5] or 0) > now:
                return None
            audit_role = row[0]
            digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(row[2]), 200_000).hex()
            if hmac.compare_digest(digest, row[3]):
                db.execute("UPDATE agent_users SET failed_attempts=0 WHERE user_id=?", (str(user_id),))
                success = True
                role = row[0]
            else:
                attempts = int(row[4] or 0) + 1
                locked = now + 15 * 60 * 1000 if attempts >= 5 else 0
                db.execute("UPDATE agent_users SET failed_attempts=?,locked_until=? WHERE user_id=?", (attempts, locked, str(user_id)))
        self.audit(user_id, audit_role, "LOGIN", "SUCCESS" if success else "FAILED")
        return role if success else None

    def authorize(self, user_id: str, role: str, permission: str) -> bool:
        role = str(role or "").upper()
        allowed = role in ROLES and ("*" in ROLE_PERMISSIONS[role] or permission in ROLE_PERMISSIONS[role])
        self.audit(user_id, role, permission, "ALLOW" if allowed else "DENY", {"permission": permission})
        return allowed

    def audit(self, user_id: str, role: str, action: str, result: str,
              details: Optional[Mapping[str, Any]] = None) -> str:
        audit_id = f"AUDIT-{uuid.uuid4().hex}"
        with sqlite3.connect(self.db_path) as db:
            db.execute("INSERT INTO agent_audit VALUES(?,?,?,?,?,?,?)",
                       (audit_id, str(user_id), str(role).upper(), str(action), str(result),
                        json.dumps(dict(details or {}), ensure_ascii=False), int(time.time() * 1000)))
        return audit_id

    def record_health(self, status: str, payload: Mapping[str, Any]) -> str:
        health_id = f"HEALTH-{uuid.uuid4().hex}"
        with sqlite3.connect(self.db_path) as db:
            db.execute("INSERT INTO agent_health VALUES(?,?,?,?)",
                       (health_id, str(status), json.dumps(dict(payload), ensure_ascii=False), int(time.time() * 1000)))
        return health_id

    def save_config_version(self, config_name: str, version: str, payload: Mapping[str, Any], *, active: bool = False) -> str:
        encoded = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True)
        version_id = f"CFG-{uuid.uuid4().hex}"
        with sqlite3.connect(self.db_path) as db:
            if active:
                db.execute("UPDATE agent_config_versions SET active=0 WHERE config_name=?", (str(config_name),))
            db.execute("INSERT INTO agent_config_versions VALUES(?,?,?,?,?,?,?)",
                       (version_id, str(config_name), str(version), encoded, hashlib.sha256(encoded.encode()).hexdigest(), int(time.time() * 1000), int(active)))
        return version_id

    def active_config(self, config_name: str) -> Optional[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as db:
            row = db.execute("SELECT payload FROM agent_config_versions WHERE config_name=? AND active=1 ORDER BY created_at DESC LIMIT 1", (str(config_name),)).fetchone()
        return json.loads(row[0]) if row else None

    def raise_alarm(self, severity: str, code: str, message: str) -> str:
        alarm_id = f"ALARM-{uuid.uuid4().hex}"
        with sqlite3.connect(self.db_path) as db:
            db.execute("INSERT INTO agent_alarms(alarm_id,severity,code,message,created_at) VALUES(?,?,?,?,?)",
                       (alarm_id, str(severity).upper(), str(code), str(message), int(time.time() * 1000)))
        return alarm_id

    def acknowledge_alarm(self, alarm_id: str, user_id: str) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.execute("UPDATE agent_alarms SET status='ACKNOWLEDGED',acknowledged_by=?,acknowledged_at=? WHERE alarm_id=? AND status='OPEN'",
                       (str(user_id), int(time.time() * 1000), str(alarm_id)))

    def queue_mes_event(self, event_id: str, endpoint: str, payload: Mapping[str, Any]) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.execute("INSERT OR IGNORE INTO mes_event_outbox(event_id,endpoint,payload,created_at) VALUES(?,?,?,?)",
                       (str(event_id), str(endpoint), json.dumps(dict(payload), ensure_ascii=False), int(time.time() * 1000)))

    def acknowledge_document(self, document_id: str, language: str, version: str, user_id: str) -> str:
        ack = f"DOC-ACK-{uuid.uuid4().hex}"
        with sqlite3.connect(self.db_path) as db:
            db.execute("INSERT INTO document_acknowledgments VALUES(?,?,?,?,?,?)",
                       (ack, document_id, language, version, user_id, int(time.time() * 1000)))
        self.audit(user_id, "OPERATOR", "DOCUMENT_ACKNOWLEDGE", "RECORDED",
                   {"documentId": document_id, "language": language, "version": version})
        return ack

    def backup_sqlite(self, backup_dir: str | Path) -> Path:
        backup_root = Path(backup_dir); backup_root.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        destination = backup_root / f"{self.db_path.stem}-{stamp}.sqlite"
        source_hash = hashlib.sha256(self.db_path.read_bytes()).hexdigest() if self.db_path.exists() else ""
        shutil.copy2(self.db_path, destination)
        self.audit("SYSTEM", "ADMIN", "SQLITE_BACKUP", "SUCCESS",
                   {"path": str(destination), "sha256": source_hash})
        return destination


__all__ = ["ROLES", "ROLE_PERMISSIONS", "LocalAgentBaseline"]

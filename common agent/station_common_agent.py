# -*- coding: utf-8 -*-
"""Common Station Agent composition layer.

Every station-specific executable remains an adapter for its equipment.  This
module owns the attributes and lifecycle shared by all agents: identity,
configuration, scanner, MES, language, alarms, history, product gates,
NG/repair, diagnostics, and health.  It deliberately contains no production
decision logic; MES remains authoritative for route, NG, retest, permissions,
and closure.

Station launchers can use ``build_common_agent(...)`` during startup and pass
the returned object to their local adapter.  The composition is lazy and
stdlib-only so it is safe for PyInstaller and for read-only smoke tests.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import socket
import sqlite3
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
import sys
import importlib.util
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Protocol

_COMPONENT_ROOT = Path(__file__).resolve().parents[1] / "station-component-reservoir" / "python"
if _COMPONENT_ROOT.exists() and str(_COMPONENT_ROOT) not in sys.path:
    sys.path.insert(0, str(_COMPONENT_ROOT))
try:
    from station_components.common import LocalAgentBaseline
except ImportError:
    LocalAgentBaseline = None

COMMON_AGENT_VERSION = "common-agent-1.0.0"
SCHEMA_VERSION = "station-agent-common-2"


@dataclass(frozen=True)
class ScanRecord:
    raw_value: str
    normalized_value: str
    scanner_id: str
    accepted: bool
    reason: str
    observed_at: int


class ScannerGateway:
    """Shared keyboard/COM/TCP/camera scan normalization and duplicate guard."""

    def __init__(self, *, duplicate_window_ms: int = 1500) -> None:
        self.duplicate_window_ms = max(0, int(duplicate_window_ms))
        self._last: Dict[str, int] = {}

    @staticmethod
    def normalize(raw_value: Any) -> str:
        return " ".join(str(raw_value or "").replace("\x00", "").strip().split())

    def accept(self, raw_value: Any, *, scanner_id: str = "unknown", now_ms: Optional[int] = None) -> ScanRecord:
        now = int(now_ms if now_ms is not None else time.time() * 1000)
        normalized = self.normalize(raw_value)
        if not normalized:
            return ScanRecord(str(raw_value or ""), "", scanner_id, False, "EMPTY_SCAN", now)
        last = self._last.get(normalized)
        if last is not None and now - last <= self.duplicate_window_ms:
            return ScanRecord(str(raw_value), normalized, scanner_id, False, "DUPLICATE_SCAN", now)
        self._last[normalized] = now
        return ScanRecord(str(raw_value), normalized, scanner_id, True, "ACCEPTED", now)


class LocalStationStore:
    """Append-only local SQLite projection for SN, NG, scans, and resource cursors."""

    def __init__(self, db_path: os.PathLike[str] | str, *, route_version: str = "unpublished") -> None:
        self.db_path = Path(db_path)
        self.route_version = route_version
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.session() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS station_sn (
              sn TEXT PRIMARY KEY, first_seen_at INTEGER NOT NULL, last_seen_at INTEGER NOT NULL,
              last_result TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS station_scans (
              event_id TEXT PRIMARY KEY, raw_value TEXT NOT NULL, normalized_value TEXT NOT NULL,
              scanner_id TEXT NOT NULL, accepted INTEGER NOT NULL, reason TEXT NOT NULL,
              observed_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS station_ng (
              event_id TEXT PRIMARY KEY, sn TEXT NOT NULL, reason TEXT NOT NULL,
              source TEXT NOT NULL, observed_at INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'ACTIVE'
            );
            CREATE TABLE IF NOT EXISTS repair_cases (
              case_id TEXT PRIMARY KEY, ng_event_id TEXT NOT NULL UNIQUE, sn TEXT NOT NULL,
              status TEXT NOT NULL, route_version TEXT NOT NULL, created_at INTEGER NOT NULL,
              closed_at INTEGER
            );
            CREATE TABLE IF NOT EXISTS repair_events (
              event_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, event_type TEXT NOT NULL,
              payload TEXT NOT NULL, created_at INTEGER NOT NULL,
              FOREIGN KEY(case_id) REFERENCES repair_cases(case_id)
            );
            CREATE TABLE IF NOT EXISTS resource_cursor (
              resource_path TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, observed_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS mes_documents (
              document_id TEXT NOT NULL, document_type TEXT NOT NULL, language TEXT NOT NULL,
              version TEXT NOT NULL, title TEXT NOT NULL DEFAULT '', content_type TEXT NOT NULL DEFAULT 'text/plain',
              content TEXT NOT NULL, sha256 TEXT NOT NULL, published_at INTEGER NOT NULL DEFAULT 0,
              fetched_at INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'PUBLISHED',
              PRIMARY KEY(document_id, language, version)
            );
            CREATE INDEX IF NOT EXISTS idx_mes_documents_current
              ON mes_documents(document_id, language, published_at DESC);
            CREATE TABLE IF NOT EXISTS document_acknowledgments (
              acknowledgment_id TEXT PRIMARY KEY, document_id TEXT NOT NULL, language TEXT NOT NULL,
              version TEXT NOT NULL, operator_id TEXT NOT NULL, acknowledged_at INTEGER NOT NULL,
              payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS station_reports (
              report_id TEXT PRIMARY KEY, report_type TEXT NOT NULL, period_start INTEGER NOT NULL,
              period_end INTEGER NOT NULL, payload TEXT NOT NULL, created_at INTEGER NOT NULL,
              status TEXT NOT NULL DEFAULT 'PENDING', attempts INTEGER NOT NULL DEFAULT 0,
              last_error TEXT NOT NULL DEFAULT '', sent_at INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_station_reports_status
              ON station_reports(status, created_at);
            CREATE TABLE IF NOT EXISTS mes_outbox (
              event_id TEXT PRIMARY KEY, endpoint TEXT NOT NULL, payload TEXT NOT NULL,
              created_at INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
              status TEXT NOT NULL DEFAULT 'PENDING', last_error TEXT NOT NULL DEFAULT '',
              sent_at INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_station_ng_sn ON station_ng(sn);
            CREATE INDEX IF NOT EXISTS idx_station_scans_value ON station_scans(normalized_value);
            """)

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.db_path), timeout=30)
        db.row_factory = sqlite3.Row
        return db

    @contextmanager
    def session(self) -> Iterable[sqlite3.Connection]:
        """Open, commit/rollback, and close one short-lived SQLite session.

        ``sqlite3.Connection`` is a context manager for transactions only; its
        ``__exit__`` does not close the connection.  Using ``connect()``
        directly in ``with`` blocks therefore left file handles open and could
        prevent Windows from deleting temporary databases or replacing station
        databases during an update.
        """
        db = self.connect()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def record_scan(self, scan: ScanRecord, event_id: str) -> None:
        with self.session() as db:
            db.execute(
                "INSERT OR IGNORE INTO station_scans VALUES(?,?,?,?,?,?,?)",
                (event_id, scan.raw_value, scan.normalized_value, scan.scanner_id,
                 int(scan.accepted), scan.reason, scan.observed_at),
            )
            if scan.accepted:
                db.execute(
                    "INSERT INTO station_sn(sn,first_seen_at,last_seen_at) VALUES(?,?,?) "
                    "ON CONFLICT(sn) DO UPDATE SET last_seen_at=excluded.last_seen_at",
                    (scan.normalized_value, scan.observed_at, scan.observed_at),
                )

    def record_ng(self, event_id: str, sn: str, reason: str, *, source: str = "EQUIPMENT",
                  observed_at: Optional[int] = None) -> None:
        observed = int(observed_at or time.time() * 1000)
        case_id = f"REPAIR-{event_id}"
        with self.session() as db:
            db.execute(
                "INSERT OR IGNORE INTO station_ng(event_id,sn,reason,source,observed_at) VALUES(?,?,?,?,?)",
                (event_id, sn, reason, source, observed),
            )
            db.execute("UPDATE station_sn SET last_result='NG' WHERE sn=?", (sn,))
            db.execute(
                "INSERT OR IGNORE INTO repair_cases(case_id,ng_event_id,sn,status,route_version,created_at) VALUES(?,?,?,?,?,?)",
                (case_id, event_id, sn, "PENDING_MES_ROUTE", self.route_version, observed),
            )

    def open_repair_case(self, case_id: str) -> Dict[str, Any]:
        with self.session() as db:
            row = db.execute("SELECT * FROM repair_cases WHERE case_id=?", (case_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown repair case: {case_id}")
        return dict(row)

    def record_repair_event(self, case_id: str, event_type: str,
                            payload: Optional[Mapping[str, Any]] = None) -> str:
        """Append a repair step; routing and closure remain MES-controlled."""
        self.open_repair_case(case_id)
        event_id = f"{case_id}-STEP-{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}"
        with self.session() as db:
            db.execute(
                "INSERT INTO repair_events(event_id,case_id,event_type,payload,created_at) VALUES(?,?,?,?,?)",
                (event_id, case_id, event_type, json.dumps(dict(payload or {}), ensure_ascii=False), int(time.time() * 1000)),
            )
            db.execute("UPDATE repair_cases SET status=? WHERE case_id=? AND status!='CLOSED'",
                       ("IN_PROGRESS", case_id))
        return event_id

    def close_repair_case(self, case_id: str, outcome: str, *, mes_authorized: bool = False) -> None:
        """Close only with an explicit MES authorization; local agents cannot self-release."""
        if not mes_authorized:
            raise PermissionError("repair closure requires MES authorization")
        self.open_repair_case(case_id)
        with self.session() as db:
            db.execute("UPDATE repair_cases SET status=?, closed_at=? WHERE case_id=?",
                       (str(outcome).upper(), int(time.time() * 1000), case_id))

    def is_ng(self, sn: str) -> bool:
        with self.session() as db:
            return db.execute("SELECT 1 FROM station_ng WHERE sn=? AND status='ACTIVE' LIMIT 1", (sn,)).fetchone() is not None

    def snapshot(self, limit: int = 100) -> Dict[str, List[Dict[str, Any]]]:
        with self.session() as db:
            sn = [dict(row) for row in db.execute("SELECT * FROM station_sn ORDER BY last_seen_at DESC LIMIT ?", (limit,))]
            ng = [dict(row) for row in db.execute("SELECT * FROM station_ng ORDER BY observed_at DESC LIMIT ?", (limit,))]
            scans = [dict(row) for row in db.execute("SELECT * FROM station_scans ORDER BY observed_at DESC LIMIT ?", (limit,))]
            repairs = [dict(row) for row in db.execute("SELECT * FROM repair_cases ORDER BY created_at DESC LIMIT ?", (limit,))]
            outbox = [dict(row) for row in db.execute("SELECT * FROM mes_outbox ORDER BY created_at DESC LIMIT ?", (limit,))]
        return {"sn": sn, "ng": ng, "scans": scans, "repairs": repairs, "outbox": outbox}

    def queue_mes(self, event_id: str, endpoint: str, payload: Mapping[str, Any]) -> None:
        with self.session() as db:
            db.execute(
                "INSERT OR IGNORE INTO mes_outbox(event_id,endpoint,payload,created_at) VALUES(?,?,?,?)",
                (event_id, endpoint, json.dumps(dict(payload), ensure_ascii=False), int(time.time() * 1000)),
            )

    def pending_mes(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self.session() as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM mes_outbox WHERE status='PENDING' ORDER BY created_at LIMIT ?", (limit,)
            )]

    def mark_mes_sent(self, event_id: str) -> None:
        with self.session() as db:
            db.execute("UPDATE mes_outbox SET status='SENT', sent_at=?, last_error='' WHERE event_id=?",
                       (int(time.time() * 1000), event_id))

    def mark_mes_failure(self, event_id: str, error: str) -> None:
        with self.session() as db:
            db.execute("UPDATE mes_outbox SET attempts=attempts+1, last_error=? WHERE event_id=?",
                       (str(error)[:500], event_id))

    def save_documents(self, documents: Sequence[Mapping[str, Any]]) -> int:
        """Upsert MES-published documents after transport and checksum validation."""
        saved = 0
        now = int(time.time() * 1000)
        with self.session() as db:
            for item in documents:
                document_id = str(item.get("documentId") or "").strip()
                language = str(item.get("language") or "").strip()
                version = str(item.get("version") or "").strip()
                if not document_id or not language or not version:
                    continue
                content = item.get("content", "")
                if not isinstance(content, str):
                    content = json.dumps(content, ensure_ascii=False, sort_keys=True)
                digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
                expected = str(item.get("sha256") or digest).lower()
                if digest != expected:
                    raise ValueError(f"document checksum mismatch: {document_id}/{language}/{version}")
                db.execute(
                    "INSERT OR REPLACE INTO mes_documents "
                    "(document_id,document_type,language,version,title,content_type,content,sha256,published_at,fetched_at,status) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (document_id, str(item.get("documentType") or "SOP"), language, version,
                     str(item.get("title") or ""), str(item.get("contentType") or "text/plain"),
                     content, digest, int(item.get("publishedAt") or 0), now,
                     str(item.get("status") or "PUBLISHED")),
                )
                saved += 1
        return saved

    def current_document(self, document_id: str, language: str) -> Optional[Dict[str, Any]]:
        with self.session() as db:
            row = db.execute(
                "SELECT * FROM mes_documents WHERE document_id=? AND language=? "
                "AND status='PUBLISHED' ORDER BY published_at DESC, fetched_at DESC LIMIT 1",
                (str(document_id), str(language)),
            ).fetchone()
        return dict(row) if row else None

    def acknowledge_document(self, document_id: str, language: str, version: str,
                             operator_id: str, payload: Optional[Mapping[str, Any]] = None) -> str:
        acknowledgment_id = f"DOC-ACK-{uuid.uuid4().hex}"
        now = int(time.time() * 1000)
        with self.session() as db:
            db.execute(
                "INSERT INTO document_acknowledgments VALUES(?,?,?,?,?,?,?)",
                (acknowledgment_id, document_id, language, version, operator_id, now,
                 json.dumps(dict(payload or {}), ensure_ascii=False)),
            )
        return acknowledgment_id

    def create_report(self, report_type: str, period_start: int, period_end: int,
                      payload: Mapping[str, Any]) -> str:
        report_id = f"REPORT-{self.db_path.stem}-{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}"
        with self.session() as db:
            db.execute(
                "INSERT INTO station_reports(report_id,report_type,period_start,period_end,payload,created_at) "
                "VALUES(?,?,?,?,?,?)",
                (report_id, str(report_type), int(period_start), int(period_end),
                 json.dumps(dict(payload), ensure_ascii=False), int(time.time() * 1000)),
            )
        return report_id

    def create_operation_report(self, *, category: str, severity: str, description: str,
                                action_taken: str = "", operator_id: str = "",
                                downtime_minutes: int = 0, occurred_at: Optional[int] = None) -> str:
        """Record an operator-reported event for MES review and audit."""
        description = str(description or "").strip()
        if not description:
            raise ValueError("operation report description is required")
        occurred = int(occurred_at or time.time() * 1000)
        payload = {
            "category": str(category or "OTHER").strip().upper(),
            "severity": str(severity or "INFO").strip().upper(),
            "description": description,
            "actionTaken": str(action_taken or "").strip(),
            "operatorId": str(operator_id or "").strip(),
            "downtimeMinutes": max(0, int(downtime_minutes or 0)),
            "occurredAt": occurred,
            "languages": ["zh-CN", "en-US", "vi-VN"],
        }
        return self.create_report("OPERATION_REPORT", occurred, occurred, payload)

    def pending_reports(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self.session() as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM station_reports WHERE status='PENDING' ORDER BY created_at LIMIT ?", (limit,)
            )]

    def mark_report_sent(self, report_id: str) -> None:
        with self.session() as db:
            db.execute("UPDATE station_reports SET status='SENT', sent_at=?, last_error='' WHERE report_id=?",
                       (int(time.time() * 1000), report_id))

    def mark_report_failure(self, report_id: str, error: str) -> None:
        with self.session() as db:
            db.execute("UPDATE station_reports SET attempts=attempts+1,last_error=? WHERE report_id=?",
                       (str(error)[:500], report_id))


class MesConnection:
    """Small idempotent MES transport used by every station adapter."""

    def __init__(self, base_url: str, store: LocalStationStore, *, preview: bool = False, timeout: float = 3.0) -> None:
        self.base_url = str(base_url or "").rstrip("/")
        self.store = store
        self.preview = bool(preview)
        self.timeout = max(0.5, float(timeout))

    def _url(self, endpoint: str) -> str:
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            return endpoint
        return self.base_url + "/" + endpoint.lstrip("/")

    def get_json(self, endpoint: str) -> Dict[str, Any]:
        """Read configuration/status from MES; never writes production facts."""
        request = urllib.request.Request(self._url(endpoint), headers={"Accept": "application/json"}, method="GET")
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            value = json.loads(response.read().decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("MES response must be an object")
        return value

    def sync_documents(self, *, station_code: str, line_code: str,
                       languages: Sequence[str] = ("zh-CN", "en-US", "vi-VN"),
                       endpoint: str = "") -> Dict[str, Any]:
        """Pull approved manuals/SOPs from MES; cached SQLite remains usable offline.

        MES response shape: {"items": [{documentId, documentType, language,
        version, title, contentType, content, sha256, publishedAt, status}]}.
        """
        if not self.base_url:
            return {"ok": False, "saved": 0, "offline": True, "items": []}
        path = endpoint or os.environ.get("MES_DOCUMENTS_ENDPOINT", "/api/station/documents")
        query = urllib.parse.urlencode({"stationCode": station_code, "lineCode": line_code,
                                         "languages": ",".join(languages)})
        try:
            data = self.get_json(path + ("&" if "?" in path else "?") + query)
            items = data.get("items", [])
            if not isinstance(items, list):
                raise ValueError("MES documents response items must be a list")
            saved = self.store.save_documents(items)
            return {"ok": True, "saved": saved, "offline": False, "items": items}
        except Exception as exc:
            return {"ok": False, "saved": 0, "offline": True, "items": [], "error": str(exc)[:500]}

    def send_reports_once(self, *, station_code: str, line_code: str,
                          endpoint: str = "", limit: int = 20) -> Dict[str, int]:
        if self.preview or not self.base_url:
            return {"sent": 0, "failed": 0, "blocked": len(self.store.pending_reports(limit))}
        target = endpoint or os.environ.get("MES_REPORTS_ENDPOINT", "/api/station/reports")
        sent = failed = 0
        for row in self.store.pending_reports(limit):
            try:
                payload = json.loads(row["payload"])
                payload.update({"reportId": row["report_id"], "reportType": row["report_type"],
                                "periodStart": row["period_start"], "periodEnd": row["period_end"],
                                "stationCode": station_code, "lineCode": line_code})
                request = urllib.request.Request(
                    self._url(target), json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    {"Content-Type": "application/json", "Idempotency-Key": row["report_id"]}, method="POST",
                )
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    response.read()
                self.store.mark_report_sent(row["report_id"])
                sent += 1
            except Exception as exc:
                self.store.mark_report_failure(row["report_id"], str(exc))
                failed += 1
        return {"sent": sent, "failed": failed, "blocked": 0}

    def queue_event(self, event: Mapping[str, Any], endpoint: str = "/api/station/events") -> str:
        event_id = str(event.get("eventId") or uuid.uuid4())
        self.store.queue_mes(event_id, self._url(endpoint), event)
        return event_id

    def queue_agent_message(self, *, station_code: str, line_code: str,
                            message_type: str, payload: Mapping[str, Any], endpoint: str = "") -> str:
        """Queue a general station-to-MES message without losing it offline."""
        event_id = f"MSG-{station_code}-{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}"
        event = {"eventId": event_id, "messageType": str(message_type),
                 "sentAt": int(time.time() * 1000), "stationCode": station_code,
                 "lineCode": line_code, "payload": dict(payload)}
        return self.queue_event(event, endpoint or os.environ.get("MES_AGENT_MESSAGES_ENDPOINT", "/api/station/agent-messages"))

    def send_pending_once(self, limit: int = 20) -> Dict[str, int]:
        """Send queued events at most once per call; duplicate event IDs are idempotent."""
        if self.preview or not self.base_url:
            return {"sent": 0, "failed": 0, "blocked": len(self.store.pending_mes(limit))}
        sent = failed = 0
        for row in self.store.pending_mes(limit):
            try:
                request = urllib.request.Request(
                    row["endpoint"], row["payload"].encode("utf-8"),
                    {"Content-Type": "application/json", "Idempotency-Key": row["event_id"]}, method="POST",
                )
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    response.read()
                self.store.mark_mes_sent(row["event_id"])
                sent += 1
            except Exception as exc:  # transport failures stay in the outbox
                self.store.mark_mes_failure(row["event_id"], str(exc))
                failed += 1
        return {"sent": sent, "failed": failed, "blocked": 0}


@dataclass(frozen=True)
class ResourceChange:
    path: str
    resource_type: str
    fingerprint: str
    changed: bool
    observed_at: int


class LocalResourceWatcher:
    """Detect new/changed Excel, CSV, SQLite, and database-export resources."""

    EXTENSIONS = {".xlsx": "EXCEL", ".xls": "EXCEL", ".csv": "CSV", ".db": "SQLITE", ".sqlite": "SQLITE"}

    def __init__(self, store: LocalStationStore, roots: Sequence[os.PathLike[str] | str]) -> None:
        self.store = store
        self.roots = [Path(root) for root in roots]

    def _files(self) -> Iterable[Path]:
        for root in self.roots:
            if root.is_file():
                yield root
            elif root.exists():
                # Resource roots can contain protected Windows folders (for
                # example printer-driver data).  A single Access Denied entry
                # must not abort station startup or its UI.
                try:
                    for current, _dirs, files in os.walk(
                        str(root), onerror=lambda _error: None
                    ):
                        for name in files:
                            path = Path(current) / name
                            if path.suffix.lower() in self.EXTENSIONS:
                                yield path
                except OSError:
                    continue

    @staticmethod
    def _fingerprint(path: Path) -> str:
        stat = path.stat()
        return hashlib.sha256(f"{stat.st_size}:{stat.st_mtime_ns}".encode("ascii")).hexdigest()

    def poll(self) -> List[ResourceChange]:
        now = int(time.time() * 1000)
        changes: List[ResourceChange] = []
        with self.store.session() as db:
            for path in self._files():
                try:
                    fingerprint = self._fingerprint(path)
                except OSError:
                    continue
                previous = db.execute("SELECT fingerprint FROM resource_cursor WHERE resource_path=?", (str(path),)).fetchone()
                changed = previous is None or previous[0] != fingerprint
                db.execute(
                    "INSERT INTO resource_cursor(resource_path,fingerprint,observed_at) VALUES(?,?,?) "
                    "ON CONFLICT(resource_path) DO UPDATE SET fingerprint=excluded.fingerprint, observed_at=excluded.observed_at",
                    (str(path), fingerprint, now),
                )
                if changed:
                    changes.append(ResourceChange(str(path), self.EXTENSIONS[path.suffix.lower()], fingerprint, True, now))
        return changes


def _host_ip() -> str:
    """Return the best local address without opening a production connection."""
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.settimeout(0.15)
        try:
            probe.connect(("192.0.2.1", 9))  # documentation-only address
            return probe.getsockname()[0]
        finally:
            probe.close()
    except OSError:
        return "127.0.0.1"


@dataclass(frozen=True)
class CommonStationConfig:
    station_code: str
    # QR printed on the physical station/machine.  A deterministic station
    # value keeps local/preview agents identifiable; production can override
    # it with STATION_MACHINE_QR after the physical label is registered in MES.
    machine_qr: str = ""
    line_domain: str = "MANUAL_LINE"
    mes_base_url: str = ""
    config_version: str = "unpublished"
    agent_version: str = COMMON_AGENT_VERSION
    module_versions: Mapping[str, str] = field(default_factory=dict)
    host_ip: str = field(default_factory=_host_ip)
    equipment_adapter: str = "generic"
    offline_policy: str = "BLOCK"
    resource_roots: Sequence[str] = field(default_factory=tuple)
    resource_read_mode: str = "changed"
    resource_recursive: bool = True
    resource_poll_seconds: int = 5
    enabled_plugins: Sequence[str] = field(default_factory=tuple)
    plugin_directory: str = "plugins"

    def validate(self) -> None:
        if not self.station_code.strip():
            raise ValueError("station_code is required")
        if self.offline_policy.upper() not in {"BLOCK", "READ_ONLY", "OUTBOX"}:
            raise ValueError("offline_policy must be BLOCK, READ_ONLY, or OUTBOX")


class CommonStationAgent:
    """Shared lifecycle and event envelope used by every station adapter."""

    MODULES = (
        "station_identity", "configuration", "scanner_gateway", "mes_connection",
        "language", "alarm", "authorization", "product_gate", "result_collector",
        "ng_repair", "history", "documents", "mes_channel", "diagnostics", "updates", "watchdog", "resource_viewer",
    )

    def __init__(self, config: CommonStationConfig, *, preview: bool = False,
                 db_path: Optional[os.PathLike[str] | str] = None,
                 resource_roots: Sequence[os.PathLike[str] | str] = ()) -> None:
        config.validate()
        from deployment_identity import check_station
        self.deployment_identity = check_station(config.station_code)
        if self.deployment_identity["status"] == "MISMATCH" and not preview:
            raise RuntimeError(
                "Station/IP configuration mismatch: "
                + json.dumps(self.deployment_identity, ensure_ascii=False)
            )
        self.config = config
        self.preview = bool(preview)
        self.instance_id = str(uuid.uuid4())
        self.started_at = int(time.time() * 1000)
        self._event_count = 0
        self._last_mes_sync: Optional[int] = None
        self.scanner = ScannerGateway()
        self.store = LocalStationStore(
            db_path or (Path.cwd() / "data" / f"{config.station_code}.sqlite"),
            route_version=config.config_version,
        )
        self.resource_roots = tuple(resource_roots or config.resource_roots)
        self.resources = LocalResourceWatcher(self.store, self.resource_roots)
        self.mes = MesConnection(config.mes_base_url, self.store, preview=self.preview)
        self.baseline = LocalAgentBaseline(self.store.db_path, config.station_code, config.line_domain) if LocalAgentBaseline else None
        self._plugins: Dict[str, Any] = {}
        self._plugin_errors: Dict[str, str] = {}

    def register_plugin(self, name: str, plugin: Any) -> None:
        """Register an adapter/plugin without allowing plugin failures to escape."""
        key = str(name).strip()
        if not key:
            raise ValueError("plugin name is required")
        self._plugins[key] = plugin
        hook = getattr(plugin, "on_register", None)
        if callable(hook):
            try:
                hook(self)
            except Exception as exc:
                self._plugin_errors[key] = f"{type(exc).__name__}: {exc}"

    def register_adapter(self, module_name: str, adapter: Any) -> None:
        """Register a canonical station module as a normal isolated plugin."""
        from station_adapter_registry import validate_adapter_name
        self.register_plugin(validate_adapter_name(module_name), adapter)

    def plugin_inventory(self) -> Dict[str, Any]:
        return {"enabled": sorted(self._plugins), "errors": dict(self._plugin_errors)}

    def run_plugin_hook(self, hook_name: str, *args, **kwargs) -> Dict[str, Any]:
        """Run an adapter hook with per-plugin isolation."""
        results = {}
        for name, plugin in tuple(self._plugins.items()):
            hook = getattr(plugin, hook_name, None)
            if not callable(hook):
                continue
            try:
                results[name] = hook(*args, **kwargs)
            except Exception as exc:
                self._plugin_errors[name] = f"{type(exc).__name__}: {exc}"
        return results

    def load_plugins(self, directory: Optional[os.PathLike[str] | str] = None) -> Dict[str, Any]:
        """Load explicitly enabled local plugins without reinstalling the Agent.

        A plugin must expose ``register(agent)`` or ``PLUGIN``. Unknown files
        are ignored; import/register failures are isolated and reported.
        Reloading replaces only that plugin and never stops the Agent loop.
        """
        root = Path(directory or self.config.plugin_directory)
        if not root.is_absolute():
            root = self.store.db_path.parent / root
        enabled = set(str(item) for item in self.config.enabled_plugins)
        loaded = []
        if not root.exists():
            return {"directory": str(root), "loaded": loaded, "errors": dict(self._plugin_errors)}
        for path in sorted(root.glob("*.py")):
            name = path.stem
            if name.startswith("_") or (enabled and name not in enabled):
                continue
            try:
                spec = importlib.util.spec_from_file_location(f"station_plugin_{name}", path)
                if not spec or not spec.loader:
                    raise ImportError("plugin loader unavailable")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                plugin = getattr(module, "PLUGIN", module)
                register = getattr(module, "register", None)
                if callable(register):
                    plugin = register(self) or plugin
                self.register_plugin(name, plugin)
                loaded.append(name)
            except Exception as exc:
                self._plugin_errors[name] = f"{type(exc).__name__}: {exc}"
        return {"directory": str(root), "loaded": loaded, "errors": dict(self._plugin_errors)}

    @property
    def station_code(self) -> str:
        return self.config.station_code

    def module_inventory(self) -> Dict[str, str]:
        """Return deterministic module/version metadata for the MES heartbeat."""
        versions = dict(self.config.module_versions)
        return {name: versions.get(name, COMMON_AGENT_VERSION) for name in self.MODULES}

    def identity(self) -> Dict[str, Any]:
        machine_qr = str(self.config.machine_qr or f"RJ-MACHINE:{self.station_code}").strip()
        return {
            "stationCode": self.station_code,
            "machineQr": machine_qr,
            "machineQrSource": "configured" if self.config.machine_qr else "derived_station_code",
            "lineDomain": self.config.line_domain,
            "processDomain": self.config.line_domain,
            "lineCode": "L004" if self.config.line_domain == "MANUAL_LINE" else self.config.line_domain,
            "hostName": socket.gethostname(),
            "hostIp": self.config.host_ip,
            "sourceIp": self.config.host_ip,
            "equipmentAdapter": self.config.equipment_adapter,
            "mesBaseUrl": self.config.mes_base_url,
            "offlinePolicy": self.config.offline_policy,
            "agentVersion": self.config.agent_version,
            "moduleVersions": self.module_inventory(),
            "configVersion": self.config.config_version,
            "commonSchemaVersion": SCHEMA_VERSION,
        }

    def health(self, *, mes_connected: bool = False, scanner_ready: bool = False,
               equipment_ready: bool = False, outbox_size: int = 0) -> Dict[str, Any]:
        return {
            **self.identity(),
            "agent": "PREVIEW" if self.preview else "READY",
            "mes": "CONNECTED" if mes_connected else "READ_ONLY" if self.preview else "DISCONNECTED",
            "scanner": "READY" if scanner_ready else "NOT_READY",
            "equipment": "READY" if equipment_ready else "NOT_READY",
            "outbox": int(outbox_size),
            "clock": "OK",
            "lastMesSyncAt": self._last_mes_sync,
            "startedAt": self.started_at,
        }

    def event(self, event_type: str, *, payload: Optional[Mapping[str, Any]] = None,
              operator: Optional[str] = None, source: str = "AGENT") -> Dict[str, Any]:
        """Create an immutable, idempotent event envelope for local/MES paths."""
        self._event_count += 1
        event_id = f"{self.station_code}-{int(time.time() * 1000)}-{self._event_count}"
        return {
            "eventId": event_id,
            "eventType": str(event_type),
            "occurredAt": int(time.time() * 1000),
            "source": source,
            "operator": operator,
            "machineQr": self.identity()["machineQr"],
            "station": self.identity(),
            "configVersion": self.config.config_version,
            "preview": self.preview,
            "payload": dict(payload or {}),
        }

    def mark_mes_sync(self) -> None:
        self._last_mes_sync = int(time.time() * 1000)

    def scan(self, raw_value: Any, *, scanner_id: str = "unknown") -> ScanRecord:
        scan = self.scanner.accept(raw_value, scanner_id=scanner_id)
        event = self.event("SCAN_ACCEPTED" if scan.accepted else "SCAN_BLOCKED",
                           payload=asdict(scan), source="SCANNER")
        self.store.record_scan(scan, event["eventId"])
        return scan

    def initialize_local_resources(self) -> Dict[str, Any]:
        """Warm the local resource cursor without blocking station startup.

        Older frozen station bundles call this hook during bootstrap.  Keep it
        deliberately read-only and tolerant of locked/missing resource files.
        """
        try:
            changes = self.poll_local_resources()
            return {"ok": True, "changed": len(changes), "stationCode": self.station_code}
        except Exception as exc:
            return {"ok": False, "changed": 0, "error": f"{type(exc).__name__}: {exc}"}

    def record_ng(self, sn: str, reason: str, *, source: str = "EQUIPMENT") -> Dict[str, Any]:
        event = self.event("NG_DETECTED", payload={"sn": sn, "reason": reason}, source=source)
        self.store.record_ng(event["eventId"], sn, reason, source=source, observed_at=event["occurredAt"])
        return event

    def poll_local_resources(self) -> List[ResourceChange]:
        # Resource discovery is diagnostic only; a locked or slow file must
        # never stop the station event loop or MES heartbeat.
        try:
            return self.resources.poll()
        except (OSError, sqlite3.Error):
            return []

    def read_local_resources(self, *, mode: Optional[str] = None, cursor: Optional[Mapping[str, int]] = None,
                             limit: int = 500, partial_limit: int = 20) -> Dict[str, Any]:
        """Read configured local resources through the shared read-only viewer."""
        from station_resource_viewer import read_resource_set
        roots = self.resource_roots or (self.store.db_path.parent,)
        sources = []
        for root in roots:
            try:
                sources.append(read_resource_set(
                    root, mode=mode or self.config.resource_read_mode,
                    cursor=cursor, recursive=self.config.resource_recursive,
                    limit=limit, partial_limit=partial_limit))
            except Exception as exc:
                sources.append({"root": str(root), "readOnly": True, "resources": [],
                                "tables": [], "error": f"{type(exc).__name__}: {exc}"})
        return {"stationCode": self.station_code, "lineDomain": self.config.line_domain,
                "readOnly": True, "sources": sources}

    def sync_documents(self, *, line_code: str = "", languages: Sequence[str] = ("zh-CN", "en-US", "vi-VN")) -> Dict[str, Any]:
        result = self.mes.sync_documents(
            station_code=self.station_code,
            line_code=line_code or self.identity()["lineCode"],
            languages=languages,
        )
        if result.get("ok"):
            self.mark_mes_sync()
        return result

    def create_report(self, report_type: str, period_start: int, period_end: int,
                      payload: Mapping[str, Any]) -> str:
        """Persist a report locally; the caller may later call ``send_reports``."""
        return self.store.create_report(report_type, period_start, period_end, payload)

    def create_operation_report(self, *, category: str, severity: str, description: str,
                                action_taken: str = "", operator_id: str = "",
                                downtime_minutes: int = 0, occurred_at: Optional[int] = None) -> str:
        description = str(description or "").strip()
        if not description:
            raise ValueError("operation report description is required")
        occurred = int(occurred_at or time.time() * 1000)
        payload = {"category": str(category or "OTHER").strip().upper(),
                   "severity": str(severity or "INFO").strip().upper(),
                   "description": description, "actionTaken": str(action_taken or "").strip(),
                   "operatorId": str(operator_id or "").strip(),
                   "downtimeMinutes": max(0, int(downtime_minutes or 0)),
                   "occurredAt": occurred, "languages": ["zh-CN", "en-US", "vi-VN"]}
        return self.create_report("OPERATION_REPORT", occurred, occurred, payload)

    def send_reports(self, *, line_code: str = "", limit: int = 20) -> Dict[str, int]:
        return self.mes.send_reports_once(
            station_code=self.station_code, line_code=line_code or self.identity()["lineCode"], limit=limit,
        )

    def send_mes_message(self, message_type: str, payload: Mapping[str, Any], *, line_code: str = "") -> str:
        return self.mes.queue_agent_message(
            station_code=self.station_code, line_code=line_code or self.identity()["lineCode"],
            message_type=message_type, payload=payload,
        )

    def snapshot(self, *, mes_connected: bool = False, scanner_ready: bool = False,
                 equipment_ready: bool = False, outbox_size: int = 0) -> Dict[str, Any]:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "identity": self.identity(),
            "health": self.health(mes_connected=mes_connected, scanner_ready=scanner_ready,
                                   equipment_ready=equipment_ready, outbox_size=outbox_size),
            "modules": list(self.MODULES),
            "plugins": self.plugin_inventory(),
            "local": {**self.store.snapshot(), "pendingReports": self.store.pending_reports(100)},
        }


def build_common_agent(station_code: str, *, line_domain: str = "MANUAL_LINE",
                       mes_base_url: str = "", config_version: str = "unpublished",
                       equipment_adapter: str = "generic", preview: bool = False,
                       module_versions: Optional[Mapping[str, str]] = None,
                       host_ip: Optional[str] = None,
                       machine_qr: Optional[str] = None,
                       db_path: Optional[os.PathLike[str] | str] = None) -> CommonStationAgent:
    """Factory used by station launchers; no MES write occurs here."""
    return CommonStationAgent(CommonStationConfig(
        station_code=station_code,
        machine_qr=str(machine_qr or os.environ.get("STATION_MACHINE_QR", "")).strip(),
        line_domain=line_domain,
        mes_base_url=mes_base_url,
        config_version=config_version,
        equipment_adapter=equipment_adapter,
        module_versions=dict(module_versions or {}),
        host_ip=host_ip or _host_ip(),
    ), preview=preview, db_path=db_path)


def load_station_config(path: os.PathLike[str] | str) -> Dict[str, Any]:
    """Load a station configuration read-only and return a validated copy."""
    file_path = Path(path)
    data = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data.get("stations"):
        raise ValueError(f"station configuration has no stations: {file_path}")
    return data


def config_fingerprint(config: Mapping[str, Any]) -> str:
    """Stable fingerprint for reporting the exact configuration revision."""
    encoded = json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "COMMON_AGENT_VERSION", "SCHEMA_VERSION", "ScanRecord", "ScannerGateway", "LocalStationStore",
    "ResourceChange", "LocalResourceWatcher", "MesConnection", "CommonStationConfig", "CommonStationAgent",
    "build_common_agent", "load_station_config", "config_fingerprint",
]

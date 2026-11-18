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
import threading
import socket
import queue
from pynput import keyboard as _pynput_keyboard
try:
    if os.name == "nt":
        from pynput.keyboard import _win32 as _pynput_keyboard_win32  # noqa: F401
except Exception:
    _pynput_keyboard_win32 = None
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence
from station_sn_client import check_ng, check_sn, register_sn

_COMPONENT_ROOT = Path(__file__).resolve().parents[1] / "station-component-reservoir" / "python"
if _COMPONENT_ROOT.exists() and str(_COMPONENT_ROOT) not in sys.path:
    sys.path.insert(0, str(_COMPONENT_ROOT))
try:
    from station_components.common import LocalAgentBaseline
except ImportError:
    LocalAgentBaseline = None

COMMON_AGENT_VERSION = "common-agent-1.0.0"
SCHEMA_VERSION = "station-agent-common-2"


def _confirmed_ng_sns(row: Mapping[str, Any]) -> List[str]:
    """Extract every MES SN identity that QR Binding treats as authoritative.

    MES NG rows are not uniform across ICT/FCT/ATE sources: some use ``sn``
    or ``mainSn`` while others publish ``productSn``, ``pcbaSn`` or
    ``boardSn``.  Dropping the latter fields makes a real NG look clear at
    downstream stations.
    """
    values: List[str] = []
    for key in ("sn", "mainSn", "productSn", "pcbaSn", "boardSn"):
        value = str(row.get(key) or "").strip().upper()
        if value and value not in values:
            values.append(value)
    return values


def announce_scan_heard() -> None:
    """Acknowledge a captured scan without blocking the station loop."""
    def speak():
        try:
            import win32com.client
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            voice.Speak("听见了", 1)
        except Exception:
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_OK)
            except Exception:
                pass
    threading.Thread(target=speak, name="scan-ack-voice", daemon=True).start()


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


class SystemScannerListener:
    """Observe fast keyboard-wedge scans system-wide without stealing keys."""
    def __init__(self, on_scan, *, scanner_id="windows-keyboard-wedge", min_chars=3, max_gap_ms=2500):
        self.on_scan = on_scan
        self.scanner_id = scanner_id
        self.min_chars = max(3, int(min_chars))
        self.max_gap = max(0.02, float(max_gap_ms) / 1000.0)
        self._buffer, self._last_at, self._listener, self._timer = [], 0.0, None, None
        self._events, self._stop = queue.Queue(), threading.Event()
        self._ui_root, self._ui_handler = None, None
        self.tcp_port = int(os.environ.get("SCANNER_TCP_PORT", "1003"))
        self._tcp_socket = None
        self.started, self.error = False, ""

    def start(self):
        if os.environ.get("STATION_DISABLE_COMMON_SCANNER", "0").strip().lower() in {"1", "true", "yes"}:
            self.started = False
            self.error = "disabled_by_station_adapter"
            return False
        if self.started:
            return True
        def run():
            try:
                self._listener = _pynput_keyboard.Listener(on_press=self._on_press)
                self._listener.start()
                self.started = True
                self._listener.join()
            except Exception as exc:
                self.error = f"keyboard listener failed: {exc}"
                self.started = False
        threading.Thread(target=run, name="system-scanner-listener", daemon=True).start()
        threading.Thread(target=self._dispatch_loop, name="scanner-event-dispatch", daemon=True).start()
        threading.Thread(target=self._tcp_loop, name="scanner-tcp-listener", daemon=True).start()
        return True

    def _dispatch_loop(self):
        while not self._stop.is_set():
            try:
                value, scanner_id = self._events.get(timeout=0.2)
                handler = self._ui_handler or self.on_scan
                announce_scan_heard()
                if self._ui_root is not None and self._ui_handler is not None:
                    self._ui_root.after(0, lambda v=value, i=scanner_id: handler(v, scanner_id=i))
                else:
                    handler(value, scanner_id=scanner_id)
            except queue.Empty: continue
            except Exception: pass

    def _emit(self, value, scanner_id):
        self._events.put((value, scanner_id))

    def bind_ui_root(self, root, handler=None):
        self._ui_root = root
        self._ui_handler = handler or self.on_scan

    def _tcp_loop(self):
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("0.0.0.0", self.tcp_port))
            server.listen(4)
            server.settimeout(1.0)
            self._tcp_socket = server
            while self.started or self._listener is None:
                try: client, _ = server.accept()
                except socket.timeout: continue
                with client:
                    raw = client.recv(4096).decode("utf-8", errors="ignore")
                    # Preserve real barcode characters (hyphen, underscore,
                    # slash, dot, etc.).  Removing punctuation changes SNs
                    # such as RJ-US-0001 and makes the MES gate miss them.
                    value = ScannerGateway.normalize(raw).upper()
                    if len(value) >= self.min_chars:
                        self._emit(value, f"tcp:{self.tcp_port}")
                        client.sendall(b"OK\r\n")
                    else: client.sendall(b"INVALID\r\n")
        except Exception as exc:
            self.error = self.error or f"TCP scanner listener failed: {exc}"

    def _on_press(self, key):
        now = time.monotonic()
        if now - self._last_at > self.max_gap:
            self._buffer = []
        self._last_at = now
        if key in (_pynput_keyboard.Key.enter, _pynput_keyboard.Key.tab) or str(key) in {"Key.enter", "Key.num_enter", "Key.tab"}:
            self._submit_buffer()
            return
        char = getattr(key, "char", None)
        if char and char.isprintable() and not char.isspace() and len(char) == 1:
            self._buffer = (self._buffer + [char])[-128:]
            if self._timer is not None: self._timer.cancel()
            self._timer = threading.Timer(0.50, self._submit_buffer)
            self._timer.daemon = True
            self._timer.start()

    def _submit_buffer(self):
        value = "".join(self._buffer).strip().upper()
        self._buffer = []
        if len(value) >= self.min_chars:
            try: self._emit(value, self.scanner_id)
            except Exception: pass

    def stop(self):
        if self._listener is not None:
            try: self._listener.stop()
            except Exception: pass
        self._stop.set()
        if self._tcp_socket is not None:
            try: self._tcp_socket.close()
            except Exception: pass
        self.started = False


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
            CREATE TABLE IF NOT EXISTS active_ng_cache (
              sn TEXT PRIMARY KEY, reason TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT 'MES_CONFIRMED_NG',
              observed_at INTEGER NOT NULL, synced_at INTEGER NOT NULL
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
            CREATE TABLE IF NOT EXISTS local_resource_reads (
              read_id INTEGER PRIMARY KEY AUTOINCREMENT,
              resource_path TEXT NOT NULL, resource_type TEXT NOT NULL,
              fingerprint TEXT NOT NULL, bytes INTEGER NOT NULL DEFAULT 0,
              modified_ns INTEGER NOT NULL DEFAULT 0, columns_json TEXT NOT NULL DEFAULT '[]',
              rows_json TEXT NOT NULL DEFAULT '[]', row_count INTEGER NOT NULL DEFAULT 0,
              read_at INTEGER NOT NULL, read_error TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_local_resource_reads_path
              ON local_resource_reads(resource_path, read_at);
            CREATE TABLE IF NOT EXISTS runtime_state (
              state_key TEXT PRIMARY KEY, state_value TEXT NOT NULL, updated_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS station_reports (
              report_id TEXT PRIMARY KEY, report_type TEXT NOT NULL, period_start INTEGER NOT NULL,
              period_end INTEGER NOT NULL, payload TEXT NOT NULL, created_at INTEGER NOT NULL,
              status TEXT NOT NULL DEFAULT 'PENDING', attempts INTEGER NOT NULL DEFAULT 0,
              last_error TEXT NOT NULL DEFAULT '', sent_at INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_station_reports_status ON station_reports(status, created_at);
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

    def cache_confirmed_ng(self, rows: Sequence[Mapping[str, Any]], *, replace_active: bool = False) -> int:
        """Cache MES confirmed-NG rows silently for fast local lookups."""
        now = int(time.time() * 1000)
        cached = 0
        with self.session() as db:
            if replace_active:
                db.execute("UPDATE station_ng SET status='CLEARED' WHERE source='MES_CONFIRMED_NG'")
                db.execute("DELETE FROM active_ng_cache")
            for row in rows:
                reason = str(row.get("defectCode") or row.get("defectDescription") or "MES_CONFIRMED_NG")
                observed = row.get("firstDetectedAt") or row.get("time") or now
                try:
                    observed = int(observed)
                except (TypeError, ValueError):
                    # MES may return ISO-8601 timestamps for older records;
                    # the local cache needs a valid observation clock value,
                    # not a failed whole-batch conversion.
                    observed = now
                for sn in _confirmed_ng_sns(row):
                    event_id = "MES-NG:" + hashlib.sha256(sn.encode("utf-8", "ignore")).hexdigest()
                    db.execute("INSERT INTO station_sn(sn,first_seen_at,last_seen_at,last_result) VALUES(?,?,?,'NG') "
                               "ON CONFLICT(sn) DO UPDATE SET last_seen_at=excluded.last_seen_at,last_result='NG'",
                               (sn, observed, observed))
                    db.execute("INSERT OR IGNORE INTO station_ng(event_id,sn,reason,source,observed_at) VALUES(?,?,?,?,?)",
                               (event_id, sn, reason, "MES_CONFIRMED_NG", observed))
                    db.execute("UPDATE station_ng SET status='ACTIVE' WHERE event_id=?", (event_id,))
                    db.execute("INSERT INTO active_ng_cache(sn,reason,source,observed_at,synced_at) VALUES(?,?,?,?,?) "
                               "ON CONFLICT(sn) DO UPDATE SET reason=excluded.reason,source=excluded.source, "
                               "observed_at=excluded.observed_at,synced_at=excluded.synced_at",
                               (sn, reason, "MES_CONFIRMED_NG", observed, now))
                    cached += 1
        self._fanout_confirmed_ng(rows)
        return cached

    def _fanout_confirmed_ng(self, rows: Sequence[Mapping[str, Any]]) -> None:
        """Mirror MES NG into this station's existing local SQLite guard tables.

        Stations keep different local schemas, so this only writes when a
        sibling database already exposes a known NG table. It never creates a
        second NG service or changes production tables.
        """
        station_dir = self.db_path.parent.parent
        for path in station_dir.glob("*.db"):
            if path.resolve() == self.db_path.resolve():
                continue
            try:
                with sqlite3.connect(str(path), timeout=2) as db:
                    tables = {r[0] for r in db.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'")}
                    if "confirmed_ng" in tables:
                        cols = {r[1] for r in db.execute("PRAGMA table_info(confirmed_ng)")}
                        for row in rows:
                            if "sn" not in cols:
                                continue
                            values = {
                                "sn": sn,
                                "source_station": str(row.get("sourceStationCode") or row.get("stationCode") or "MES"),
                                "source_station_code": str(row.get("sourceStationCode") or row.get("stationCode") or "MES"),
                                "batch_id": str(row.get("batchId") or row.get("batch_id") or ""),
                                "reason": str(row.get("defectCode") or row.get("defectDescription") or "MES_CONFIRMED_NG"),
                                "result": "NG",
                                "test_time": str(row.get("firstDetectedAt") or ""),
                                "source_table": "MES_8080_NG_GUARD",
                                "received_at": int(time.time() * 1000),
                                "confirmed_at": int(time.time() * 1000),
                                "updated_at": int(time.time() * 1000),
                            }
                            for sn in _confirmed_ng_sns(row):
                                values["sn"] = sn
                                names = [c for c in cols if c in values]
                                if names:
                                    marks = ",".join("?" for _ in names)
                                    db.execute(
                                        f"INSERT OR IGNORE INTO confirmed_ng ({','.join(names)}) VALUES ({marks})",
                                        [values[c] for c in names],
                                    )
                    if "mes_confirmed_ng_cache" in tables:
                        cols = {r[1] for r in db.execute("PRAGMA table_info(mes_confirmed_ng_cache)")}
                        if "sn" in cols:
                            for row in rows:
                                values = {
                                    "source_station": str(row.get("sourceStationCode") or row.get("stationCode") or "MES"),
                                    "batch_id": str(row.get("batchId") or ""),
                                    "payload": json.dumps(dict(row), ensure_ascii=False),
                                    "registry_version": 0,
                                    "synced_at": int(time.time() * 1000),
                                }
                                for sn in _confirmed_ng_sns(row):
                                    values["sn"] = sn
                                    names = [c for c in cols if c in values]
                                    db.execute(
                                        f"INSERT OR IGNORE INTO mes_confirmed_ng_cache ({','.join(names)}) VALUES ({','.join('?' for _ in names)})",
                                        [values[c] for c in names],
                                    )
            except Exception:
                continue

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
            return db.execute("SELECT 1 FROM active_ng_cache WHERE sn=? UNION ALL "
                              "SELECT 1 FROM station_ng WHERE sn=? AND status='ACTIVE' LIMIT 1", (sn, sn)).fetchone() is not None

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

    def create_report(self, report_type: str, period_start: int, period_end: int,
                      payload: Mapping[str, Any]) -> str:
        report_id = f"REPORT-{self.db_path.stem}-{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}"
        with self.session() as db:
            db.execute("INSERT INTO station_reports(report_id,report_type,period_start,period_end,payload,created_at) VALUES(?,?,?,?,?,?)",
                       (report_id, str(report_type), int(period_start), int(period_end),
                        json.dumps(dict(payload), ensure_ascii=False), int(time.time() * 1000)))
        return report_id

    def pending_reports(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self.session() as db:
            return [dict(row) for row in db.execute("SELECT * FROM station_reports WHERE status='PENDING' ORDER BY created_at LIMIT ?", (limit,))]


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

    def queue_event(self, event: Mapping[str, Any], endpoint: str = "/api/station/events") -> str:
        event_id = str(event.get("eventId") or uuid.uuid4())
        self.store.queue_mes(event_id, self._url(endpoint), event)
        return event_id

    def queue_agent_message(self, *, station_code: str, line_code: str,
                            message_type: str, payload: Mapping[str, Any], endpoint: str = "") -> str:
        event_id = f"MSG-{station_code}-{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}"
        return self.queue_event({"eventId": event_id, "messageType": str(message_type),
                                 "sentAt": int(time.time() * 1000), "stationCode": station_code,
                                 "lineCode": line_code, "payload": dict(payload)},
                                endpoint or os.environ.get("MES_AGENT_MESSAGES_ENDPOINT", "/api/station/agent-messages"))

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

    EXTENSIONS = {".xlsx": "EXCEL", ".xls": "EXCEL", ".xlsm": "EXCEL", ".csv": "CSV",
                  ".json": "JSON", ".html": "HTML", ".htm": "HTML",
                  ".db": "SQLITE", ".sqlite": "SQLITE"}
    SKIP_DIRS = {"build", "dist", "_internal", "__pycache__", ".git", ".venv", "node_modules", "$recycle.bin"}

    def __init__(self, store: LocalStationStore, roots: Sequence[os.PathLike[str] | str]) -> None:
        self.store = store
        self.roots = [Path(root) for root in roots]

    def _files(self) -> Iterable[Path]:
        for root in self.roots:
            if root.is_file():
                yield root
            elif root.exists():
                try:
                    for current, dirs, files in os.walk(str(root), onerror=lambda _error: None):
                        dirs[:] = [d for d in dirs if d.lower() not in self.SKIP_DIRS]
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
    line_domain: str = "AUTO_LINE"
    mes_base_url: str = ""
    config_version: str = "unpublished"
    agent_version: str = COMMON_AGENT_VERSION
    module_versions: Mapping[str, str] = field(default_factory=dict)
    host_ip: str = field(default_factory=_host_ip)
    equipment_adapter: str = "generic"
    offline_policy: str = "BLOCK"

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
        "ng_repair", "history", "documents", "mes_channel", "operation_report", "diagnostics", "updates", "watchdog",
    )

    def __init__(self, config: CommonStationConfig, *, preview: bool = False,
                 db_path: Optional[os.PathLike[str] | str] = None,
                 resource_roots: Sequence[os.PathLike[str] | str] = ()) -> None:
        config.validate()
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
        self.resources = LocalResourceWatcher(self.store, resource_roots)
        self.mes = MesConnection(config.mes_base_url, self.store, preview=self.preview)
        self.baseline = LocalAgentBaseline(self.store.db_path, config.station_code, config.line_domain) if LocalAgentBaseline else None
        self.system_scanner = SystemScannerListener(self.scan)
        self.system_scanner.start()
        threading.Thread(target=self._confirmed_ng_cache_loop,
                         name=f"{config.station_code}-mes-ng-cache", daemon=True).start()

    def _confirmed_ng_cache_loop(self) -> None:
        """Keep a silent local mirror of MES confirmed NG."""
        version = 0
        first_sync = True
        while True:
            try:
                from station_sn_client import fetch_confirmed_ng
                snapshot = fetch_confirmed_ng(version)
                if not snapshot.get("unchanged"):
                    rows = snapshot.get("items") or []
                    self.store.cache_confirmed_ng(rows, replace_active=first_sync)
                    first_sync = False
                    version = int(snapshot.get("version") or version)
            except Exception:
                pass
            # Manual stations need the same fast local NG gate as QR Binding;
            # the loop remains silent and never blocks the operator UI.
            time.sleep(5 if self.config.line_domain == "MANUAL_LINE" else 15)

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
            "lineCode": "L002" if self.config.line_domain == "AUTO_LINE" else self.config.line_domain,
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
        if scan.accepted:
            # The MES NG mirror is the fast scan-time gate.  The background
            # cache loop refreshes it; never make the operator wait on a
            # full/network NG query here.
            if self.store.is_ng(scan.normalized_value):
                allowed, code, detail = False, "MES_NG", {
                    "sn": scan.normalized_value, "source": "LOCAL_SQLITE"
                }
            else:
                allowed, code, detail = True, "NO_NG", {
                    "sn": scan.normalized_value, "source": "LOCAL_SQLITE"
                }
            if allowed:
                allowed, code, detail = check_sn(scan.normalized_value, self.station_code)
            if not allowed:
                scan = ScanRecord(scan.raw_value, scan.normalized_value, scan.scanner_id,
                                  False, code, scan.observed_at)
                self.store.record_scan(scan, self.event("SCAN_BLOCKED", payload={"detail": detail}, source="SN_SYNC")["eventId"])
                return scan
            registered, register_code, register_detail = register_sn(scan.normalized_value, self.station_code)
            if not registered:
                scan = ScanRecord(scan.raw_value, scan.normalized_value, scan.scanner_id,
                                  False, register_code, scan.observed_at)
                self.store.record_scan(scan, self.event("SCAN_BLOCKED", payload={"detail": register_detail}, source="SN_SYNC")["eventId"])
                return scan
        event = self.event("SCAN_ACCEPTED" if scan.accepted else "SCAN_BLOCKED",
                           payload=asdict(scan), source="SCANNER")
        self.store.record_scan(scan, event["eventId"])
        return scan

    def bind_ui_root(self, root, handler=None) -> None:
        self.system_scanner.bind_ui_root(root, handler or self.scan)

    def record_ng(self, sn: str, reason: str, *, source: str = "EQUIPMENT") -> Dict[str, Any]:
        event = self.event("NG_DETECTED", payload={"sn": sn, "reason": reason}, source=source)
        self.store.record_ng(event["eventId"], sn, reason, source=source, observed_at=event["occurredAt"])
        # Every locally detected NG must enter the durable MES outbox so MES
        # can confirm and broadcast it to downstream stations.  The outbox
        # worker handles 155/122 delivery and retry without blocking the UI.
        try:
            self.mes.queue_event(event, endpoint="/api/station/events")
        except Exception:
            pass
        return event

    def local_confirmed_ng(self, sn: str):
        """Return the last MES confirmed-NG cache row without network I/O."""
        code = str(sn or "").strip().upper()
        if not code:
            return None
        if self.store.is_ng(code):
            return {"sn": code, "source": "LOCAL_SQLITE", "code": "MES_NG"}
        return None

    def poll_local_resources(self) -> List[ResourceChange]:
        return self.resources.poll()

    def initialize_local_resources(self, *, limit: int = 10000) -> Dict[str, Any]:
        """Read all supported resources once into append-only local SQLite."""
        marker = "local_resources.initial_read.v1"
        with self.store.session() as db:
            row = db.execute("SELECT state_value FROM runtime_state WHERE state_key=?", (marker,)).fetchone()
        if row and row[0] == "complete":
            return {"status": "already_complete", "resources": 0, "errors": 0}
        from station_resource_viewer import read_resource_set
        roots = self.resources.roots or (self.store.db_path.parent,)
        read_count = errors = 0
        with self.store.session() as db:
            for root in roots:
                source = read_resource_set(root, mode="startup", recursive=True, limit=min(limit, 10000))
                table_by_path = {str(item.get("path")): item for item in source.get("tables", [])}
                for item in source.get("resources", []):
                    path = str(item.get("path", "")); table = table_by_path.get(path, {})
                    error = str(table.get("error", "")); errors += int(bool(error))
                    rows = table.get("rows", [])
                    db.execute(
                        "INSERT INTO local_resource_reads "
                        "(resource_path,resource_type,fingerprint,bytes,modified_ns,columns_json,rows_json,row_count,read_at,read_error) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (path, str(item.get("extension", "")).upper().lstrip("."),
                         str(item.get("modified_ns", "")), int(item.get("bytes", 0) or 0),
                         int(item.get("modified_ns", 0) or 0),
                         json.dumps(table.get("columns", []), ensure_ascii=False),
                         json.dumps(rows, ensure_ascii=False, default=str), len(rows),
                         int(time.time() * 1000), error),
                    )
                    # Silently index historical SN/NG rows into the same local
                    # SQLite used by the scanner gate.  Resource formats vary
                    # by station, so use conservative aliases and never invent
                    # an SN when the source row has none.
                    sn_keys = ("sn", "psn", "pcb_sn", "pcba_sn", "board_sn",
                               "serial_no", "serial_number", "serialNumber",
                               "motherboard_sn", "main_sn")
                    result_keys = ("result", "status", "test_result", "outcome",
                                   "判定", "结果", "ng")
                    ng_values = {"NG", "FAIL", "FAILED", "NOK", "ERROR", "REWORK"}
                    for row_index, raw_row in enumerate(rows):
                        if not isinstance(raw_row, dict):
                            continue
                        normalized = {str(k).strip().lower(): v for k, v in raw_row.items()}
                        sn_value = ""
                        for key in sn_keys:
                            value = normalized.get(key.lower())
                            if value not in (None, ""):
                                sn_value = str(value).strip().upper()
                                break
                        if not sn_value:
                            continue
                        observed = int(item.get("modified_ns", 0) or time.time() * 1000)
                        db.execute(
                            "INSERT INTO station_sn(sn,first_seen_at,last_seen_at) VALUES(?,?,?) "
                            "ON CONFLICT(sn) DO UPDATE SET last_seen_at=excluded.last_seen_at",
                            (sn_value, observed, observed),
                        )
                        result_value = ""
                        for key in result_keys:
                            value = normalized.get(key.lower())
                            if value not in (None, ""):
                                result_value = str(value).strip().upper()
                                break
                        if result_value in ng_values:
                            event_id = f"RESOURCE-NG:{hashlib.sha256((path + ':' + str(row_index) + ':' + sn_value).encode('utf-8', 'ignore')).hexdigest()}"
                            db.execute(
                                "INSERT OR IGNORE INTO station_ng(event_id,sn,reason,source,observed_at) VALUES(?,?,?,?,?)",
                                (event_id, sn_value, result_value, "LOCAL_RESOURCE_HISTORY", observed),
                            )
                            db.execute("UPDATE station_sn SET last_result='NG' WHERE sn=?", (sn_value,))
                    read_count += 1
            db.execute("CREATE TABLE IF NOT EXISTS runtime_state (state_key TEXT PRIMARY KEY, state_value TEXT NOT NULL, updated_at INTEGER NOT NULL)")
            db.execute("INSERT OR REPLACE INTO runtime_state(state_key,state_value,updated_at) VALUES(?,?,?)",
                       (marker, "complete", int(time.time() * 1000)))
        return {"status": "complete", "resources": read_count, "errors": errors}

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
        report_id = self.store.create_report("OPERATION_REPORT", occurred, occurred, payload)
        self.mes.queue_event({"eventId": report_id, "eventType": "OPERATION_REPORT",
                              "occurredAt": occurred, "station": self.identity(), "payload": payload},
                             endpoint=os.environ.get("MES_REPORTS_ENDPOINT", "/api/station/reports"))
        return report_id

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
            "local": {**self.store.snapshot(), "pendingReports": self.store.pending_reports(100)},
        }


def build_common_agent(station_code: str, *, line_domain: str = "AUTO_LINE",
                       mes_base_url: str = "", config_version: str = "unpublished",
                       equipment_adapter: str = "generic", preview: bool = False,
                       module_versions: Optional[Mapping[str, str]] = None,
                       host_ip: Optional[str] = None,
                       machine_qr: Optional[str] = None,
                       db_path: Optional[os.PathLike[str] | str] = None,
                       resource_roots: Sequence[os.PathLike[str] | str] = ()) -> CommonStationAgent:
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
    ), preview=preview, db_path=db_path, resource_roots=resource_roots)


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
    "COMMON_AGENT_VERSION", "SCHEMA_VERSION", "ScanRecord", "ScannerGateway", "SystemScannerListener", "LocalStationStore",
    "ResourceChange", "LocalResourceWatcher", "MesConnection", "CommonStationConfig", "CommonStationAgent",
    "build_common_agent", "load_station_config", "config_fingerprint",
]

# -*- coding: utf-8 -*-
"""Shared ATE data/scan backend.

The station UIs remain station-specific.  This module owns the common
contracts: recursive resource discovery, per-file SQLite checkpoints, local
duplicate/NG guards, and a callback for live UI updates.
"""
from __future__ import annotations

import sqlite3
import threading
import time
import os
import csv
import difflib
import json
import sqlite3 as _sqlite3
import xml.etree.ElementTree as ET
import unicodedata
import urllib.request
import urllib.error
import subprocess
import uuid
from html.parser import HTMLParser
from pathlib import Path


SUPPORTED_SUFFIXES = {".xlsx", ".xlsm", ".xls", ".csv", ".json", ".html", ".htm", ".xml", ".txt", ".tsv", ".log", ".db", ".sqlite", ".sqlite3"}
DEFAULT_MES_ENDPOINTS = (
    "http://192.168.6.155:8080",
    "http://192.168.6.122:8080",
    "http://127.0.0.1:8080",
)
MES_NG_SOURCES_NOT_FOR_DOWNSTREAM_ATE = {"manu_ict", "manu_fct", "auto_ict", "auto_fct"}
MES_NG_REFRESH_INTERVAL_SECONDS = 3.0

FIELD_ALIASES = {
    "sn": ("sn", "barcode", "bar code", "serial", "serial no", "serial number", "条码", "序列号", "序列号sn"),
    "result": ("result", "test result", "status", "outcome", "pass fail", "测试结果", "结果", "判定"),
    "time": ("time", "test time", "date time", "datetime", "timestamp", "测试时间", "时间", "日期"),
    "channel": ("channel", "slot", "position", "side", "station", "通道", "位置", "工位"),
    "error": ("error", "error code", "fail item", "ng item", "defect", "错误", "错误代码", "不良项目"),
}


def _fuzzy_label(value):
    return "".join(str(value or "").strip().lower().replace("_", "").replace("-", "").split())


def _infer_columns(row):
    normalized = [_fuzzy_label(value) for value in row]
    found = {}
    for field, aliases in FIELD_ALIASES.items():
        candidates = []
        for index, label in enumerate(normalized):
            if not label:
                continue
            scores = []
            for alias in aliases:
                target = _fuzzy_label(alias)
                score = 1.0 if label == target else 0.92 if target in label or label in target else difflib.SequenceMatcher(None, label, target).ratio()
                scores.append(score)
            best = max(scores) if scores else 0
            if best >= 0.68:
                candidates.append((best, index))
        if candidates:
            found[field] = max(candidates)[1]
    return found


def parse_matrix_fuzzy(matrix):
    """Parse a flexible worksheet matrix using fuzzy header inference."""
    header = None
    header_row = 0
    for row_no, row in enumerate(matrix[:120], 1):
        found = _infer_columns(row)
        core_columns = [found.get(field) for field in ("sn", "result", "time")]
        # Reject parameter/limit rows that fuzzy-match every field to the
        # same cell. A real result header has distinct SN/result/time columns.
        if {"sn", "result", "time"}.issubset(found) and len(set(core_columns)) == 3:
            header, header_row = found, row_no
            break
    if not header:
        return []
    parsed = []
    for row_no, row in enumerate(matrix[header_row:], header_row + 1):
        values = list(row)
        def value(field):
            index = header.get(field)
            return values[index] if index is not None and index < len(values) else ""
        sn = str(value("sn") or "").strip().upper()
        result = str(value("result") or "").strip().upper()
        test_time = str(value("time") or "").strip()
        if not sn or not test_time:
            continue
        if result not in {"PASS", "FAIL", "NG", "OK", "NOK", "合格", "不合格"}:
            continue
        result = "FAIL" if result in {"FAIL", "NG", "NOK", "不合格"} else "PASS"
        channel = str(value("channel") or "").strip().upper() or str(row_no - header_row)
        parsed.append({"source_row": row_no, "sn": sn, "result": result,
                       "channel": channel, "side": channel[:1] if channel[:1] in {"L", "R"} else "S",
                       "test_time": test_time, "error_code": str(value("error") or "").strip()})
    return parsed


def flexible_parse_file(path):
    """Read Excel/CSV using fuzzy headers; unsupported files return no rows."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        for encoding in ("utf-8-sig", "gb18030", "cp1252"):
            try:
                with path.open("r", encoding=encoding, newline="") as handle:
                    return parse_matrix_fuzzy(list(csv.reader(handle)))
            except UnicodeDecodeError:
                continue
        return []
    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            records = payload if isinstance(payload, list) else payload.get("records", payload.get("data", [])) if isinstance(payload, dict) else []
            if not isinstance(records, list):
                return []
            return parse_matrix_fuzzy([list(records[0].keys())] + [list(item.values()) for item in records if isinstance(item, dict)]) if records and isinstance(records[0], dict) else []
        except Exception:
            return []
    if path.suffix.lower() == ".xml":
        try:
            root = ET.parse(str(path)).getroot()
            records = []
            for element in root.iter():
                children = list(element)
                if children and all(not list(child) for child in children):
                    records.append({child.tag: (child.text or "").strip() for child in children})
            if records:
                return parse_matrix_fuzzy([list(records[0].keys())] + [list(item.values()) for item in records])
        except Exception:
            pass
        return []
    if path.suffix.lower() in {".txt", ".tsv", ".log"}:
        try:
            lines = path.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
            sample = "\n".join(lines[:5])
            delimiter = "\t" if "\t" in sample else "|" if "|" in sample else ","
            return parse_matrix_fuzzy([next(csv.reader([line], delimiter=delimiter)) for line in lines if line.strip()])
        except Exception:
            return []
    if path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
        try:
            db = _sqlite3.connect(str(path))
            tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            for table in tables:
                columns = [row[1] for row in db.execute(f'PRAGMA table_info("{table}")')]
                rows = db.execute(f'SELECT * FROM "{table}" LIMIT 5000').fetchall()
                parsed = parse_matrix_fuzzy([columns] + [list(row) for row in rows])
                if parsed:
                    db.close(); return parsed
            db.close()
        except Exception:
            pass
        return []
    if path.suffix.lower() in {".html", ".htm"}:
        try:
            class TableParser(HTMLParser):
                def __init__(self):
                    super().__init__(); self.rows=[]; self.row=[]; self.cell=[]; self.in_cell=False
                def handle_starttag(self, tag, attrs):
                    if tag in {"td", "th"}: self.cell=[]; self.in_cell=True
                    elif tag == "tr": self.row=[]
                def handle_data(self, data):
                    if self.in_cell: self.cell.append(data)
                def handle_endtag(self, tag):
                    if tag in {"td", "th"}:
                        self.row.append("".join(self.cell).strip()); self.in_cell=False
                    elif tag == "tr" and self.row: self.rows.append(self.row)
            parser = TableParser(); parser.feed(path.read_text(encoding="utf-8", errors="ignore"))
            return parse_matrix_fuzzy(parser.rows)
        except Exception:
            return []
    if path.suffix.lower() == ".xls":
        return []
    try:
        from openpyxl import load_workbook
        workbook = load_workbook(str(path), read_only=True, data_only=True)
        rows = []
        for sheet_index, sheet in enumerate(workbook.worksheets):
            parsed = parse_matrix_fuzzy(list(sheet.iter_rows(values_only=True)))
            for item in parsed:
                item["source_row"] = sheet_index * 1000000 + item["source_row"]
            rows.extend(parsed)
        workbook.close()
        return rows
    except Exception:
        return []


class AteCommonAgent:
    def __init__(self, db_path, watch_dir=None, parser=None,
                 station_code="", mes_sync=None):
        self.db_path = Path(db_path)
        self.watch_dir = Path(watch_dir or os.environ.get("ATE_WATCH_DIR", r"D:\ATS\测试报表"))
        self.parser = parser
        self.station_code = station_code
        self.mes_sync = mes_sync
        configured = os.environ.get("ATE_MES_ENDPOINTS", "")
        self.mes_endpoints = tuple(
            item.strip().rstrip("/") for item in configured.split(",") if item.strip()
        ) or DEFAULT_MES_ENDPOINTS
        self.active_mes_endpoint = self.mes_endpoints[0]
        self._lock = threading.RLock()
        self._listeners = []
        self._file_state = {}
        self._watch_thread = None
        self._observer = None
        self._history_thread = None
        self._mes_history_thread = None
        self._mes_history_initialized = False
        self._mes_refresh_thread = None
        self._mes_refresh_lock = threading.Lock()
        self._last_mes_refresh_ms = 0
        self._scanner_listener = None
        self._scanner_buffer = ""
        self._scanner_lock = threading.Lock()
        self._scanner_callback = None
        self._watch_stop = threading.Event()
        self._focused_file = None
        self._last_full_scan_ms = 0
        self._full_scan_interval_ms = 10000
        self._init_db()

    def connect(self):
        db = sqlite3.connect(str(self.db_path), timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def _init_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS atecommon_checkpoint(
              source_file TEXT PRIMARY KEY,
              last_source_row INTEGER NOT NULL DEFAULT 0,
              updated_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS atecommon_scan_guard(
              sn TEXT PRIMARY KEY,
              result TEXT NOT NULL,
              reason TEXT NOT NULL DEFAULT '',
              source_station TEXT NOT NULL DEFAULT '',
              updated_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_atecommon_guard_result
              ON atecommon_scan_guard(result);
            CREATE TABLE IF NOT EXISTS atecommon_seen_sn(
              sn TEXT PRIMARY KEY,
              first_station TEXT NOT NULL DEFAULT '',
              updated_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS atecommon_mes_seen_sn(
              sn TEXT PRIMARY KEY,
              source_station TEXT NOT NULL DEFAULT '',
              updated_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS atecommon_parsed_ng(
              sn TEXT PRIMARY KEY,
              source_file TEXT NOT NULL DEFAULT '',
              result TEXT NOT NULL DEFAULT 'NG',
              reason TEXT NOT NULL DEFAULT '',
              parsed_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS atecommon_local_records(
              source_file TEXT NOT NULL,
              source_row INTEGER NOT NULL,
              sn TEXT NOT NULL,
              result TEXT NOT NULL DEFAULT '',
              test_time TEXT NOT NULL DEFAULT '',
              channel TEXT NOT NULL DEFAULT '',
              recorded_at INTEGER NOT NULL,
              PRIMARY KEY(source_file, source_row)
            );
            CREATE TABLE IF NOT EXISTS atecommon_mes_ng_cache(
              sn TEXT PRIMARY KEY,
              source_station TEXT NOT NULL DEFAULT 'MES',
              reason TEXT NOT NULL DEFAULT '',
              received_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS atecommon_mes_outbox(
              event_id TEXT PRIMARY KEY,
              event_json TEXT NOT NULL,
              sent_at INTEGER,
              retry_count INTEGER NOT NULL DEFAULT 0,
              last_error TEXT NOT NULL DEFAULT '',
              created_at INTEGER NOT NULL
            );
            """)
            try:
                db.execute("ALTER TABLE atecommon_parsed_ng ADD COLUMN result TEXT NOT NULL DEFAULT 'NG'")
            except sqlite3.OperationalError:
                pass

    def add_listener(self, callback):
        if callback not in self._listeners:
            self._listeners.append(callback)

    def set_watch_dir(self, path):
        """Change the recursive data-source path at runtime."""
        new_path = Path(path).expanduser()
        if not new_path.exists() or not new_path.is_dir():
            raise ValueError(f"Data source directory does not exist: {new_path}")
        self.watch_dir = new_path
        self._file_state.clear()
        self._focused_file = None
        self._last_full_scan_ms = 0
        return self.watch_dir

    def mes_endpoint_order(self):
        """Return primary/fallback MES order: 155, 122, then localhost."""
        return self.mes_endpoints

    def set_active_mes_endpoint(self, endpoint):
        """Set the active MES endpoint and announce only real endpoint changes."""
        endpoint = str(endpoint or "").rstrip("/")
        if not endpoint or endpoint == self.active_mes_endpoint:
            return False
        previous = self.active_mes_endpoint
        self.active_mes_endpoint = endpoint

        def speak():
            text = f"MES通讯已切换，当前使用{endpoint}。"
            try:
                import win32com.client
                voice = win32com.client.Dispatch("SAPI.SpVoice")
                voice.Volume = 100
                voice.Rate = 0
                voice.Speak(text, 0)
            except Exception:
                return

        threading.Thread(target=speak, name="ate-common-mes-switch-voice", daemon=True).start()
        return previous

    def _emit(self, rows):
        if not rows:
            return
        for callback in tuple(self._listeners):
            try:
                callback(rows)
            except Exception:
                continue

    @staticmethod
    def _row_is_ng(row):
        value = str(row.get("result", row.get("status", "")) or "").strip().upper()
        return value in {"NG", "FAIL", "FAILED", "NOK", "ERROR"}

    def _cache_parsed_ng(self, rows, announce=True):
        for row in rows or []:
            if not self._row_is_ng(row):
                continue
            sn = self.normalize_scan(row.get("sn", ""))
            if not sn:
                continue
            reason = str(row.get("error", row.get("error_code", "LOCAL PARSED NG")) or "LOCAL PARSED NG")
            source = Path(str(row.get("source_file", "LOCAL FILE"))).name
            with self.connect() as db:
                db.execute(
                    "INSERT INTO atecommon_parsed_ng(sn,source_file,result,reason,parsed_at) VALUES(?,?,?,?,?) "
                    "ON CONFLICT(sn) DO UPDATE SET source_file=excluded.source_file,result=excluded.result,reason=excluded.reason,parsed_at=excluded.parsed_at",
                    (sn, source, str(row.get("result", "NG")), reason, int(time.time() * 1000)),
                )
            # Batch announcement is handled once by announce_updates(), so
            # do not speak one separate message for every NG row.
            self.update_ng(sn, reason, source, announce=False)
            self._queue_mes_ng(sn, reason)

    def _mes_event_url(self, endpoint):
        endpoint = str(endpoint or "").rstrip("/")
        if endpoint.endswith("/api/pda/events"):
            return endpoint
        if "/api/" in endpoint:
            return endpoint.split("/api/", 1)[0] + "/api/pda/events"
        return endpoint + "/api/pda/events"

    def _queue_mes_ng(self, sn, reason):
        """Queue a local ATE NG so MES can fan it out to other stations."""
        now = int(time.time() * 1000)
        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self.station_code}|{sn}"))
        event = {
            "eventId": event_id,
            "type": "NG_DEFECT",
            "stationCode": self.station_code,
            "payload": {
                "sn": sn,
                "result": "FAIL",
                "errorCode": reason,
                "sourceStationCode": self.station_code,
                "eventType": "ate_common_file",
            },
        }
        with self.connect() as db:
            db.execute(
                "INSERT INTO atecommon_mes_outbox(event_id,event_json,sent_at,retry_count,last_error,created_at) "
                "VALUES(?,?,NULL,0,'',?) ON CONFLICT(event_id) DO UPDATE SET event_json=excluded.event_json",
                (event_id, json.dumps(event, ensure_ascii=False), now),
            )

    def _sync_mes_outbox(self, limit=20):
        with self.connect() as db:
            pending = db.execute(
                "SELECT event_id,event_json FROM atecommon_mes_outbox WHERE sent_at IS NULL "
                "ORDER BY created_at LIMIT ?", (limit,)
            ).fetchall()
        sent = 0
        for item in pending:
            last_error = "MES unavailable"
            for endpoint in self.mes_endpoints:
                try:
                    request = urllib.request.Request(
                        self._mes_event_url(endpoint),
                        data=item["event_json"].encode("utf-8"),
                        headers={"Content-Type": "application/json", "Idempotency-Key": item["event_id"]},
                        method="POST",
                    )
                    with urllib.request.urlopen(request, timeout=5) as response:
                        response.read()
                    with self.connect() as db:
                        db.execute(
                            "UPDATE atecommon_mes_outbox SET sent_at=?,retry_count=retry_count+1,last_error='' WHERE event_id=?",
                            (int(time.time() * 1000), item["event_id"]),
                        )
                    sent += 1
                    break
                except urllib.error.HTTPError as exc:
                    if exc.code == 409:
                        with self.connect() as db:
                            db.execute(
                                "UPDATE atecommon_mes_outbox SET sent_at=?,retry_count=retry_count+1,last_error='' WHERE event_id=?",
                                (int(time.time() * 1000), item["event_id"]),
                            )
                        sent += 1
                        break
                    last_error = f"HTTP {exc.code}"
                except Exception as exc:
                    last_error = str(exc)[:300]
            else:
                with self.connect() as db:
                    db.execute(
                        "UPDATE atecommon_mes_outbox SET retry_count=retry_count+1,last_error=? WHERE event_id=?",
                        (last_error, item["event_id"]),
                    )
        return sent

    def _record_local_rows(self, rows):
        """Persist every parsed SN/result, including PASS and NG, locally."""
        if not rows:
            return
        now = int(time.time() * 1000)
        with self.connect() as db:
            for row in rows:
                sn = self.normalize_scan(row.get("sn", ""))
                source_file = str(row.get("source_file", ""))
                source_row = int(row.get("source_row") or 0)
                if not sn or not source_file or source_row <= 0:
                    continue
                db.execute(
                    "INSERT OR REPLACE INTO atecommon_local_records "
                    "(source_file,source_row,sn,result,test_time,channel,recorded_at) VALUES(?,?,?,?,?,?,?)",
                    (source_file, source_row, sn, str(row.get("result", "")),
                     str(row.get("test_time", "")), str(row.get("channel", "")), now),
                )

    def announce_updates(self, rows):
        """Speak one common update message for every station UI."""
        count = len(rows or [])
        if count <= 0:
            return

        def speak():
            names = sorted({Path(str(row.get("source_file", ""))).name
                            for row in rows or [] if row.get("source_file")})
            file_text = names[0] if names else "未知文件"
            if len(names) > 1:
                file_text = f"{file_text}等{len(names)}个文件"
            ng_count = sum(1 for row in rows or [] if self._row_is_ng(row))
            if not ng_count:
                return
            text = f"发现{ng_count}个不良品，请立即取出。"
            try:
                import win32com.client
                voice = win32com.client.Dispatch("SAPI.SpVoice")
                voice.Volume = 100
                voice.Rate = 0
                voice.Speak(text, 0)
            except Exception:
                # Keep the update visible even when the COM voice bridge is
                # unavailable on a station image.
                try:
                    safe = text.replace("'", "''")
                    subprocess.Popen(
                        ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command",
                         "Add-Type -AssemblyName System.Speech;"
                         "$v=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                         f"$v.Volume=100;$v.Rate=0;$v.Speak('{safe}')"],
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                except Exception:
                    return

        threading.Thread(target=speak, name="ate-common-update-voice", daemon=True).start()

    def resource_files(self):
        if not self.watch_dir.exists():
            return []
        files = []
        for path in self.watch_dir.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue
            if path.name.startswith("~$"):
                continue
            try:
                if path.stat().st_size:
                    files.append(path)
            except OSError:
                continue
        return sorted(files, key=lambda item: (item.stat().st_mtime_ns, item.name), reverse=True)

    def _checkpoint(self, path):
        with self.connect() as db:
            row = db.execute(
                "SELECT last_source_row FROM atecommon_checkpoint WHERE source_file=?",
                (str(path),),
            ).fetchone()
        return int(row[0]) if row else 0

    def ingest_all(self, emit=True):
        """Parse every file, but emit only rows after that file's checkpoint."""
        if self.parser is None:
            raise RuntimeError("AteCommonAgent requires a parser callback")
        added = []
        for path in self.resource_files():
            rows = self.parser(path) or []
            last_row = self._checkpoint(path)
            new_rows = [row for row in rows if int(row.get("source_row") or 0) > last_row]
            if new_rows:
                maximum = max(int(row.get("source_row") or 0) for row in rows)
                now = int(time.time() * 1000)
                with self.connect() as db:
                    db.execute(
                        "INSERT INTO atecommon_checkpoint VALUES(?,?,?) "
                        "ON CONFLICT(source_file) DO UPDATE SET "
                        "last_source_row=excluded.last_source_row,updated_at=excluded.updated_at",
                        (str(path), maximum, now),
                    )
                for row in new_rows:
                    item = dict(row)
                    item["source_file"] = str(path)
                    added.append(item)
        if emit:
            self._record_local_rows(added)
            self._cache_parsed_ng(added, announce=True)
            self._emit(added)
            self.announce_updates(added)
        else:
            self._record_local_rows(added)
            self._cache_parsed_ng(added, announce=False)
        return added

    def start_initial_history_read(self):
        """Read all existing file contents once, silently in the background."""
        if self._history_thread and self._history_thread.is_alive():
            return self._history_thread

        def history_worker():
            try:
                self.ingest_all(emit=False)
            except Exception:
                # History recovery must not stop the live watcher.
                return

        self._history_thread = threading.Thread(
            target=history_worker, name="ate-common-initial-history", daemon=True)
        self._history_thread.start()
        return self._history_thread

    def _file_signature(self, path):
        stat = path.stat()
        return (int(stat.st_mtime_ns), int(stat.st_size))

    def changed_files(self, paths=None):
        """Return recursively changed files, newest changed file first."""
        current = dict(self._file_state) if paths is not None else {}
        changed = []
        scan_paths = list(paths) if paths is not None else self.resource_files()
        for path in scan_paths:
            try:
                signature = self._file_signature(path)
            except OSError:
                continue
            current[str(path)] = signature
            if self._file_state.get(str(path)) != signature:
                changed.append(path)
        self._file_state = current
        return sorted(changed, key=lambda item: item.stat().st_mtime_ns, reverse=True)

    def _watch_paths(self, now_ms):
        """Full scan first, then focused-file polling with periodic rescan."""
        if not self._file_state:
            all_files = self.resource_files()
            self._last_full_scan_ms = now_ms
            return all_files
        if not self._focused_file or now_ms - self._last_full_scan_ms >= self._full_scan_interval_ms:
            all_files = self.resource_files()
            self._last_full_scan_ms = now_ms
            return all_files
        focused = Path(self._focused_file)
        return [focused] if focused.exists() else self.resource_files()

    def ingest_changed(self, include_existing=False, full_scan_interval=10.0, paths=None):
        """Process only changed files; prioritize the file updated most recently."""
        if self.parser is None:
            raise RuntimeError("AteCommonAgent requires a parser callback")
        self._full_scan_interval_ms = max(1000, int(float(full_scan_interval) * 1000))
        scan_paths = paths if paths is not None else self._watch_paths(int(time.time() * 1000))
        paths = self.changed_files(scan_paths)
        if not include_existing and not self._file_state:
            return []
        added = []
        for path in paths:
            rows = self.parser(path) or []
            last_row = self._checkpoint(path)
            new_rows = [row for row in rows if int(row.get("source_row") or 0) > last_row]
            if not new_rows:
                continue
            maximum = max(int(row.get("source_row") or 0) for row in rows)
            now = int(time.time() * 1000)
            with self.connect() as db:
                db.execute(
                    "INSERT INTO atecommon_checkpoint VALUES(?,?,?) "
                    "ON CONFLICT(source_file) DO UPDATE SET last_source_row=excluded.last_source_row,updated_at=excluded.updated_at",
                    (str(path), maximum, now),
                )
            for row in new_rows:
                item = dict(row)
                item["source_file"] = str(path)
                item["focused_file"] = str(path) == str(paths[0])
                added.append(item)
        if paths:
            self._focused_file = str(paths[0])
        self._record_local_rows(added)
        self._cache_parsed_ng(added, announce=True)
        self._emit(added)
        self.announce_updates(added)
        return added

    def start_watching(self, interval=1.0, include_existing=False):
        """Start the recursive watcher. Safe to call more than once."""
        if self._watch_thread and self._watch_thread.is_alive():
            return self._watch_thread
        self._watch_stop.clear()
        if not self._file_state:
            self.changed_files()
        if include_existing:
            self.start_initial_history_read()
        self.start_mes_history_sync()

        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer

            owner = self

            class Handler(FileSystemEventHandler):
                def on_created(self, event):
                    if not event.is_directory:
                        owner.ingest_changed(paths=[Path(event.src_path)])

                def on_modified(self, event):
                    if not event.is_directory:
                        owner.ingest_changed(paths=[Path(event.src_path)])

            self._observer = Observer()
            self._observer.schedule(Handler(), str(self.watch_dir), recursive=True)
            self._observer.start()
        except Exception:
            self._observer = None

        def loop():
            while not self._watch_stop.wait(max(0.2, float(interval))):
                try:
                    # Watchdog handles immediate updates. This is only the
                    # periodic recursive safety scan for missed events.
                    now = int(time.time() * 1000)
                    if now - self._last_full_scan_ms >= self._full_scan_interval_ms:
                        self.ingest_changed(full_scan_interval=interval * 10,
                                            paths=self.resource_files())
                except Exception:
                    continue

        self._watch_thread = threading.Thread(target=loop, name="ate-common-file-watch", daemon=True)
        self._watch_thread.start()
        return self._watch_thread

    def stop_watching(self):
        self._watch_stop.set()
        if getattr(self, "_observer", None):
            self._observer.stop()
            self._observer.join(timeout=2)
            self._observer = None
        if self._watch_thread and self._watch_thread.is_alive():
            self._watch_thread.join(timeout=2)
        self._watch_thread = None
        if self._history_thread and self._history_thread.is_alive():
            self._history_thread.join(timeout=2)
        self._history_thread = None
        if self._mes_history_thread and self._mes_history_thread.is_alive():
            self._mes_history_thread.join(timeout=2)
        self._mes_history_thread = None
        self.stop_scanner()

    def start_scanner(self, callback):
        """Start the shared keyboard-wedge scanner capture for every station."""
        self._scanner_callback = callback
        if self._scanner_listener and self._scanner_listener.is_alive():
            return self._scanner_listener
        try:
            from pynput import keyboard
        except Exception:
            return None

        def on_press(key):
            try:
                char = getattr(key, "char", None)
                if char and char.isprintable() and char not in "\\r\\n\\t":
                    with self._scanner_lock:
                        self._scanner_buffer += char
                    return
                if key in (keyboard.Key.enter, keyboard.Key.tab):
                    with self._scanner_lock:
                        raw, self._scanner_buffer = self._scanner_buffer, ""
                    normalized = self.normalize_scan(raw)
                    if normalized and self._scanner_callback:
                        self._scanner_callback(normalized, "keyboard-wedge")
            except Exception:
                return

        self._scanner_listener = keyboard.Listener(on_press=on_press)
        self._scanner_listener.start()
        return self._scanner_listener

    def stop_scanner(self):
        listener = self._scanner_listener
        self._scanner_listener = None
        self._scanner_callback = None
        with self._scanner_lock:
            self._scanner_buffer = ""
        if listener:
            try:
                listener.stop()
            except Exception:
                pass

    @staticmethod
    def normalize_scan(raw_sn):
        """Normalize keyboard-wedge scans consistently for every station.

        Scanner input may contain full-width characters, CR/LF, tabs, or
        other control characters depending on the keyboard layout and scan
        gun configuration.  SNs are normalized here before any NG/DUP rule.
        """
        value = unicodedata.normalize("NFKC", str(raw_sn or ""))
        value = "".join(ch for ch in value if ch.isprintable() and ch not in "\\r\\n\\t")
        return value.strip().upper()

    def update_ng(self, sn, reason="", source_station="", announce=True):
        sn = self.normalize_scan(sn)
        if not sn:
            return
        with self.connect() as db:
            db.execute(
                "INSERT INTO atecommon_scan_guard(sn,result,reason,source_station,updated_at) "
                "VALUES(?,?,?,?,?) ON CONFLICT(sn) DO UPDATE SET result=excluded.result, "
                "reason=excluded.reason,source_station=excluded.source_station,updated_at=excluded.updated_at",
                (sn, "NG", reason, source_station or self.station_code, int(time.time() * 1000)),
            )
        if announce:
            self.announce_ng(sn, source_station or self.station_code)

    def announce_ng(self, sn, source_station=""):
        """Announce any new local or MES NG with source and SN."""
        sn = str(sn or "").strip().upper()
        source_station = str(source_station or self.station_code)
        if not sn:
            return

        self._announce_ng_text("发现1个不良品，请立即取出。")

    def _announce_ng_text(self, text):
        def speak():
            try:
                import win32com.client
                voice = win32com.client.Dispatch("SAPI.SpVoice")
                voice.Volume = 100
                voice.Rate = 0
                voice.Speak(text, 0)
            except Exception:
                return

        threading.Thread(target=speak, name="ate-common-ng-voice", daemon=True).start()

    def announce_ng_count(self, count):
        count = int(count or 0)
        if count > 0:
            self._announce_ng_text(f"发现{count}个不良品，请立即取出。")

    def update_mes_ng(self, sn, reason="", source_station="MES"):
        """Cache an NG received from MES/another station and announce it."""
        source_key = str(source_station or "").strip().lower()
        if source_key in MES_NG_SOURCES_NOT_FOR_DOWNSTREAM_ATE or source_key == self.station_code.strip().lower():
            return
        sn = self.normalize_scan(sn)
        if not sn:
            return
        with self.connect() as db:
            db.execute(
                "INSERT INTO atecommon_mes_ng_cache(sn,source_station,reason,received_at) VALUES(?,?,?,?) "
                "ON CONFLICT(sn) DO UPDATE SET source_station=excluded.source_station,reason=excluded.reason,received_at=excluded.received_at",
                (sn, source_station or "MES", reason, int(time.time() * 1000)),
            )
        self.update_ng(sn, reason, source_station)

    def sync_mes_ng_history(self, force=False):
        """Load MES active-NG SNs and announce only newly received ones."""
        if not force:
            with self.connect() as db:
                if db.execute("SELECT 1 FROM atecommon_mes_ng_cache LIMIT 1").fetchone():
                    return 0
        for base in self.mes_endpoints:
            try:
                request = urllib.request.Request(
                    base.rstrip("/") + "/api/station/ng-guard",
                    headers={"Accept": "application/json"},
                )
                with urllib.request.urlopen(request, timeout=15) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                items = payload.get("items", []) if isinstance(payload, dict) else []
                rows = []
                now = int(time.time() * 1000)
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    sn = self.normalize_scan(item.get("sn") or item.get("code"))
                    if not sn:
                        continue
                    station = str(item.get("sourceStation") or item.get("stationCode") or item.get("source") or "MES")
                    station = str(item.get("sourceStationCode") or station)
                    station_key = station.strip().lower()
                    if station_key in MES_NG_SOURCES_NOT_FOR_DOWNSTREAM_ATE or station_key == self.station_code.strip().lower():
                        continue
                    reason = str(item.get("reason") or item.get("error") or item.get("defect") or "MES NG")
                    received = int(item.get("time") or item.get("createdAt") or now)
                    rows.append((sn, station, reason, received))
                with self.connect() as db:
                    existing = {row[0] for row in db.execute(
                        "SELECT sn FROM atecommon_mes_ng_cache")}
                new_rows = [row for row in rows if row[0] not in existing]
                if not rows:
                    self._mes_history_initialized = True
                    return 0
                with self.connect() as db:
                    db.executemany(
                        "INSERT INTO atecommon_mes_ng_cache(sn,source_station,reason,received_at) VALUES(?,?,?,?) "
                        "ON CONFLICT(sn) DO UPDATE SET source_station=excluded.source_station,reason=excluded.reason,received_at=excluded.received_at",
                        rows,
                    )
                    db.executemany(
                        "INSERT INTO atecommon_scan_guard(sn,result,reason,source_station,updated_at) VALUES(?,?,?,?,?) "
                        "ON CONFLICT(sn) DO UPDATE SET result='NG',reason=excluded.reason,source_station=excluded.source_station,updated_at=excluded.updated_at",
                        [(sn, "NG", reason, station, received) for sn, station, reason, received in rows],
                    )
                if self._mes_history_initialized and new_rows:
                    self.announce_ng_count(len(new_rows))
                self._mes_history_initialized = True
                return len(rows)
            except Exception:
                continue
        return 0

    def start_mes_history_sync(self):
        """Keep the MES NG cache current without blocking the UI."""
        if self._mes_history_thread and self._mes_history_thread.is_alive():
            return self._mes_history_thread

        def loop():
            self.sync_mes_ng_history(force=True)
            self._sync_mes_outbox()
            while not self._watch_stop.wait(MES_NG_REFRESH_INTERVAL_SECONDS):
                try:
                    self.sync_mes_ng_history(force=True)
                    self._sync_mes_outbox()
                except Exception:
                    continue

        self._mes_history_thread = threading.Thread(
            target=loop,
            name="ate-common-mes-ng-history",
            daemon=True,
        )
        self._mes_history_thread.start()
        return self._mes_history_thread

    def start_mes_background_refresh(self):
        """Refresh MES slowly in the background after a scan decision."""
        now = int(time.time() * 1000)
        with self._mes_refresh_lock:
            if now - self._last_mes_refresh_ms < 5000:
                return self._mes_refresh_thread
            if self._mes_refresh_thread and self._mes_refresh_thread.is_alive():
                return self._mes_refresh_thread
            self._last_mes_refresh_ms = now
            self._mes_refresh_thread = threading.Thread(
                target=lambda: self.sync_mes_ng_history(force=True),
                name="ate-common-mes-background-refresh",
                daemon=True,
            )
            self._mes_refresh_thread.start()
            return self._mes_refresh_thread

    def update_mes_duplicate(self, sn, source_station="MES"):
        """Cache MES duplicate evidence for fast local scanner checks."""
        sn = self.normalize_scan(sn)
        if not sn:
            return
        with self.connect() as db:
            db.execute(
                "INSERT INTO atecommon_mes_seen_sn(sn,source_station,updated_at) VALUES(?,?,?) "
                "ON CONFLICT(sn) DO UPDATE SET source_station=excluded.source_station,updated_at=excluded.updated_at",
                (sn, source_station, int(time.time() * 1000)),
            )

    def check_scan(self, raw_sn):
        sn = self.normalize_scan(raw_sn)
        if not sn:
            return {"sn": "", "status": "EMPTY", "blocked": True, "detail": "SN is empty"}
        with self.connect() as db:
            ng = db.execute(
                "SELECT reason,source_station FROM atecommon_scan_guard WHERE sn=? AND result='NG'",
                (sn,),
            ).fetchone()
            duplicate = db.execute(
                "SELECT first_station FROM atecommon_seen_sn WHERE sn=?", (sn,)
            ).fetchone()
            mes_duplicate = db.execute(
                "SELECT source_station FROM atecommon_mes_seen_sn WHERE sn=?", (sn,)
            ).fetchone()
        if ng:
            return {"sn": sn, "status": "NG", "blocked": True,
                    "detail": ng["reason"] or "MES confirmed NG"}
        if duplicate:
            return {"sn": sn, "status": "DUPLICATE", "blocked": True,
                    "detail": f"Already seen at {duplicate['first_station'] or 'ATE'}"}
        if mes_duplicate:
            return {"sn": sn, "status": "MES_DUPLICATE", "blocked": True,
                    "detail": f"MES already recorded at {mes_duplicate['source_station'] or 'MES'}"}
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO atecommon_seen_sn(sn,first_station,updated_at) VALUES(?,?,?)",
                (sn, self.station_code, int(time.time() * 1000)),
            )
        return {"sn": sn, "status": "CLEAR", "blocked": False, "detail": ""}


__all__ = ["AteCommonAgent", "SUPPORTED_SUFFIXES"]

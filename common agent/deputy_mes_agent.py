# -*- coding: utf-8 -*-
"""Local-first Deputy MES gateway for manual-line stations.

The gateway accepts station events into SQLite first, then forwards them to
MES when reachable.  It is intentionally stdlib-only so the frozen EXE can run
on low-power station computers without the project Python environment.
"""
from __future__ import annotations

import json
import os
import sqlite3
import socket
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4
from urllib.parse import urlparse


APP_DIR = Path(os.environ.get("DEPUTY_MES_HOME", Path(__file__).resolve().parent))
APP_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.environ.get("DEPUTY_MES_DB", APP_DIR / "deputy_mes.sqlite"))
MES_URLS = [
    item.strip().rstrip("/")
    for item in os.environ.get(
        "DEPUTY_MES_URLS",
        "http://192.168.6.155:8080/api/pda/events,http://192.168.6.122:8080/api/pda/events",
    ).split(",")
    if item.strip()
]
MES_URL = MES_URLS[0] if MES_URLS else "http://192.168.6.155:8080/api/pda/events"
HOST = os.environ.get("DEPUTY_MES_HOST", "127.0.0.1")
PORT = int(os.environ.get("DEPUTY_MES_PORT", "8765"))
SYNC_SECONDS = max(2, int(os.environ.get("DEPUTY_MES_SYNC_SECONDS", "10")))


def now_ms() -> int:
    return int(time.time() * 1000)


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self.conn:
            self.conn.execute(
                """CREATE TABLE IF NOT EXISTS deputy_events(
                    event_id TEXT PRIMARY KEY,
                    station_code TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT NOT NULL DEFAULT '',
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )"""
            )
            self.conn.execute(
                """CREATE TABLE IF NOT EXISTS deputy_station_merges(
                    merge_key TEXT PRIMARY KEY,
                    ict_event_id TEXT NOT NULL DEFAULT '',
                    fct_event_id TEXT NOT NULL DEFAULT '',
                    depanel_event_id TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                )"""
            )
            self.conn.execute(
                """CREATE TABLE IF NOT EXISTS deputy_deliveries(
                    event_id TEXT NOT NULL,
                    target TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT NOT NULL DEFAULT '',
                    updated_at INTEGER NOT NULL,
                    PRIMARY KEY(event_id, target)
                )"""
            )

    @staticmethod
    def merge_key(payload: Dict[str, Any]) -> str:
        wanted = {
            "motherboardsn", "motherboard_sn", "mainsn", "main_sn", "boardsn",
            "board_sn", "serialnumber", "serial_number", "sn", "serial",
        }
        found = []
        def visit(value: Any) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    if str(key).lower().replace("-", "_") in wanted and isinstance(item, (str, int)):
                        text = str(item).strip().upper()
                        if text and text not in found:
                            found.append(text)
                    visit(item)
            elif isinstance(value, list):
                for item in value:
                    visit(item)
        visit(payload)
        return found[0] if found else ""

    def merge_event(self, event_id: str, station: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        name = station.lower()
        category = "ict" if "ict" in name else "fct" if "fct" in name else "depanel" if ("depanel" in name or "分板" in name) else ""
        key = self.merge_key(payload)
        if not category or not key:
            return {"mergeKey": key, "mergeStatus": "UNMATCHED"}
        with self.lock, self.conn:
            row = self.conn.execute("SELECT * FROM deputy_station_merges WHERE merge_key=?", (key,)).fetchone()
            values = {"ict_event_id": "", "fct_event_id": "", "depanel_event_id": ""}
            if row:
                values.update(dict(row))
            values[category + "_event_id"] = event_id
            ready = all(values[name + "_event_id"] for name in ("ict", "fct", "depanel"))
            status = "READY_LOCAL" if ready else "WAITING_STATIONS"
            self.conn.execute(
                "INSERT INTO deputy_station_merges(merge_key,ict_event_id,fct_event_id,depanel_event_id,status,updated_at) VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(merge_key) DO UPDATE SET ict_event_id=excluded.ict_event_id,fct_event_id=excluded.fct_event_id,depanel_event_id=excluded.depanel_event_id,status=excluded.status,updated_at=excluded.updated_at",
                (key, values["ict_event_id"], values["fct_event_id"], values["depanel_event_id"], status, now_ms()),
            )
            return {"mergeKey": key, "mergeStatus": status}

    def put(self, event_id: str, station: str, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock, self.conn:
            row = self.conn.execute("SELECT * FROM deputy_events WHERE event_id=?", (event_id,)).fetchone()
            if row:
                stamp = now_ms()
                for target in MES_URLS:
                    self.conn.execute(
                        "INSERT OR IGNORE INTO deputy_deliveries(event_id,target,status,updated_at) VALUES(?,?,?,?)",
                        (event_id, target, "PENDING", stamp),
                    )
                return dict(row)
            stamp = now_ms()
            self.conn.execute(
                "INSERT INTO deputy_events(event_id,station_code,event_type,payload,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                (event_id, station, event_type, json.dumps(payload, ensure_ascii=False), "PENDING_MES", stamp, stamp),
            )
            for target in MES_URLS:
                self.conn.execute(
                    "INSERT OR IGNORE INTO deputy_deliveries(event_id,target,status,updated_at) VALUES(?,?,?,?)",
                    (event_id, target, "PENDING", stamp),
                )
            return dict(self.conn.execute("SELECT * FROM deputy_events WHERE event_id=?", (event_id,)).fetchone())

    def pending(self, limit: int = 50):
        with self.lock:
            return self.conn.execute(
                "SELECT e.*, d.target, d.status AS delivery_status FROM deputy_events e JOIN deputy_deliveries d ON d.event_id=e.event_id "
                "WHERE d.status IN ('PENDING','RETRY') ORDER BY e.created_at LIMIT ?", (limit,)
            ).fetchall()

    def mark(self, event_id: str, target: str, status: str, error: str = "") -> None:
        with self.lock, self.conn:
            self.conn.execute(
                "UPDATE deputy_deliveries SET status=?, attempts=attempts+1, last_error=?, updated_at=? WHERE event_id=? AND target=?",
                (status, error[:1000], now_ms(), event_id, target),
            )
            remaining = self.conn.execute(
                "SELECT COUNT(*) FROM deputy_deliveries WHERE event_id=? AND status IN ('PENDING','RETRY')", (event_id,)
            ).fetchone()[0]
            event_status = "SENT" if not remaining else ("RETRY" if status == "RETRY" else "PENDING_MES")
            self.conn.execute(
                "UPDATE deputy_events SET status=?, attempts=attempts+1, last_error=?, updated_at=? WHERE event_id=?",
                (event_status, error[:1000], now_ms(), event_id),
            )

    def counts(self):
        with self.lock:
            rows = self.conn.execute("SELECT status,COUNT(*) n FROM deputy_events GROUP BY status").fetchall()
        return {r["status"]: r["n"] for r in rows}

    def merge_ready_count(self) -> int:
        with self.lock:
            return int(self.conn.execute("SELECT COUNT(*) FROM deputy_station_merges WHERE status='READY_LOCAL'").fetchone()[0])


STORE = Store(DB_PATH)
ACTIVE_TARGET = None
TARGET_LOCK = threading.Lock()


def target_reachable(url: str) -> bool:
    try:
        parsed = urlparse(url)
        with socket.create_connection((parsed.hostname, parsed.port or 80), timeout=1.0):
            return True
    except Exception:
        return False


def send_to_mes(row: sqlite3.Row) -> None:
    global ACTIVE_TARGET
    payload = json.loads(row["payload"])
    failures = []
    target = row["target"]
    request = urllib.request.Request(
        target,
        json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        {"Content-Type": "application/json", "Idempotency-Key": row["event_id"], "X-Deputy-MES": "1", "X-Deputy-Replica": "1"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            if response.status >= 400:
                raise RuntimeError(f"MES HTTP {response.status}")
        with TARGET_LOCK:
            ACTIVE_TARGET = target
    except Exception as exc:
        failures.append(f"{target}: {exc}")
        raise RuntimeError("; ".join(failures))


def sync_loop() -> None:
    while True:
        for row in STORE.pending():
            try:
                send_to_mes(row)
                STORE.mark(row["event_id"], row["target"], "SENT")
            except Exception as exc:
                STORE.mark(row["event_id"], row["target"], "RETRY", str(exc))
        time.sleep(SYNC_SECONDS)


class Handler(BaseHTTPRequestHandler):
    server_version = "RUIJING-DeputyMES/1.0"

    def log_message(self, *_args):
        return

    def reply(self, status: int, body: Dict[str, Any]) -> None:
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path.startswith("/api/mes/ng-check"):
            # The Deputy has no authority to invent NG records.  An empty
            # result means "no locally known NG"; the queued MES sync remains
            # responsible for the authoritative server-side record.
            self.reply(200, {"ok": True, "found": False, "records": [], "mode": "LOCAL_PENDING"})
            return
        if self.path.rstrip("/") == "/health":
            reachability = {target: target_reachable(target) for target in MES_URLS}
            with TARGET_LOCK:
                active = ACTIVE_TARGET
            self.reply(200, {
                "ok": True, "mode": "DEPUTY_MES",
                "primary": MES_URLS[0] if MES_URLS else None,
                "backup": MES_URLS[1] if len(MES_URLS) > 1 else None,
                "activeMes": active,
                "reachable": reachability,
                "queue": STORE.counts(),
                "ictFctDepanelReady": STORE.merge_ready_count(),
            })
            return
        if self.path.rstrip("/") == "/api/deputy/merged":
            with STORE.lock:
                rows = [dict(row) for row in STORE.conn.execute("SELECT * FROM deputy_station_merges ORDER BY updated_at DESC LIMIT 200")]
            self.reply(200, {"ok": True, "merges": rows})
            return
        if self.path.rstrip("/") == "/api/deputy/pending":
            self.reply(200, {"events": [dict(row) for row in STORE.pending(200)]})
            return
        self.reply(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        if self.path.rstrip("/") == "/api/station/shell-bindings/commit":
            try:
                size = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(size).decode("utf-8") or "{}")
                board = str(body.get("pcbaSn") or body.get("pcba_sn") or "").strip().upper()
                shell = str(body.get("shellSn") or body.get("shell_sn") or "").strip().upper()
                if not board or not shell:
                    self.reply(400, {"ok": False, "code": "MISSING_SN"})
                    return
                event_id = str(uuid4())
                event = {"eventId": event_id, "type": "shell_binding_commit",
                         "stationCode": body.get("stationCode") or "manu_shellbinding",
                         "payload": {"pcbaSn": board, "shellSn": shell, "operator": body.get("operator", "")}}
                STORE.put(event_id, event["stationCode"], event["type"], event)
                self.reply(200, {"ok": True, "acknowledgementId": event_id,
                                 "eventId": event_id, "mode": "LOCAL_ACCEPTED", "offline": True})
            except Exception as exc:
                self.reply(400, {"ok": False, "code": "INVALID_BINDING", "error": str(exc)})
            return
        if self.path.rstrip("/") not in {"/api/deputy/events", "/api/pda/events"}:
            self.reply(404, {"ok": False, "error": "not_found"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(size).decode("utf-8"))
            if not isinstance(body, dict):
                raise ValueError("event must be a JSON object")
            event_id = str(body.get("eventId") or body.get("event_id") or uuid4())
            station = str(body.get("stationCode") or body.get("station") or "UNKNOWN")
            event_type = str(body.get("type") or body.get("eventType") or "station_event")
            row = STORE.put(event_id, station, event_type, body)
            merge = STORE.merge_event(event_id, station, body)
            self.reply(200, {"ok": True, "eventId": event_id, "mode": "LOCAL_ACCEPTED", "status": row["status"], **merge})
        except Exception as exc:
            self.reply(400, {"ok": False, "error": str(exc)})


def main() -> None:
    threading.Thread(target=sync_loop, name="deputy-mes-sync", daemon=True).start()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Deputy MES listening on http://{HOST}:{PORT}; MES={MES_URL}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()

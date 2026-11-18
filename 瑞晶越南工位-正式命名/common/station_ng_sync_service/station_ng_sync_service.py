# -*- coding: utf-8 -*-
"""Standalone per-computer MES confirmed-NG synchronizer and local API."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from station_ng_sync import NgBroadcastSync
from mes_direct_fallback import install as install_mes_direct_fallback

# The standalone 8089 service is the shared local gateway for all stations;
# it must use the same 155 -> 122 MES failover as the station UIs.
install_mes_direct_fallback()

PORT = int(os.environ.get("STATION_NG_SYNC_PORT", "8089"))
DB_PATH = Path(os.environ.get(
    "RJ_NG_SYNC_DB",
    str(Path(__file__).resolve().parent / "data" / "common_ng_sync.sqlite"),
))
MES_URL = os.environ.get("MES_API_URL", "http://192.168.6.155:8080/api/pda/events")


def init_sn_ledger():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(DB_PATH), timeout=10) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS sn_station_arrivals(
            id INTEGER PRIMARY KEY AUTOINCREMENT, sn TEXT NOT NULL,
            station_code TEXT NOT NULL, source_type TEXT NOT NULL DEFAULT 'SCANNER',
            arrived_at INTEGER NOT NULL, result TEXT NOT NULL DEFAULT 'ARRIVED',
            UNIQUE(sn, station_code))""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_sn_arrivals_sn ON sn_station_arrivals(sn)")


def sn_check(sn, station_code):
    code, station = str(sn or "").strip().upper(), str(station_code or "").strip()
    with sqlite3.connect(str(DB_PATH), timeout=3) as db:
        rows = db.execute(
            "SELECT station_code,arrived_at,result FROM sn_station_arrivals WHERE sn=? ORDER BY arrived_at",
            (code,),
        ).fetchall()
    same = next((row for row in rows if row[0] == station), None)
    return {"sn": code, "stationCode": station, "duplicate": bool(same),
            "arrivals": [{"stationCode": r[0], "arrivedAt": r[1], "result": r[2]} for r in rows]}


def sn_register(sn, station_code, source_type="SCANNER"):
    code, station = str(sn or "").strip().upper(), str(station_code or "").strip()
    if not code or not station:
        return {"ok": False, "code": "SN_AND_STATION_REQUIRED"}
    now = int(time.time() * 1000)
    try:
        with sqlite3.connect(str(DB_PATH), timeout=10) as db:
            db.execute(
                "INSERT INTO sn_station_arrivals(sn,station_code,source_type,arrived_at) VALUES(?,?,?,?)",
                (code, station, str(source_type or "SCANNER").upper(), now),
            )
        return {"ok": True, "sn": code, "stationCode": station, "arrivedAt": now}
    except sqlite3.IntegrityError:
        return {"ok": False, "code": "DUPLICATE_SN_AT_STATION", **sn_check(code, station)}


class NgSyncHandler(BaseHTTPRequestHandler):
    sync = None

    def log_message(self, *_args):
        return

    def _json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path in {"/health", "/api/health"}:
            self._json({"status": "ok", "service": "station-ng-sync", "port": PORT})
            return
        if parsed.path in {"/ng_check", "/api/ng_check"}:
            sn = (urllib.parse.parse_qs(parsed.query).get("sn") or [""])[0].strip().upper()
            with sqlite3.connect(str(DB_PATH), timeout=3) as db:
                row = db.execute(
                    "SELECT source_station,reason,received_at FROM mes_ng_cache WHERE sn=?", (sn,)
                ).fetchone()
            records = ([{"station_code": row[0], "reason": row[1], "received_at": row[2], "repair_status": "pending"}]
                       if row else [])
            self._json({"found": bool(records), "records": records})
            return
        if parsed.path in {"/sn_check", "/api/sn/check"}:
            query = urllib.parse.parse_qs(parsed.query)
            self._json(sn_check((query.get("sn") or [""])[0], (query.get("stationCode") or [""])[0]))
            return
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path not in {"/sn_register", "/api/sn/register"}:
            self._json({"error": "not found"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            result = sn_register(body.get("sn"), body.get("stationCode"), body.get("sourceType", "SCANNER"))
            self._json(result, 200 if result.get("ok") else 409)
        except Exception as exc:
            self._json({"ok": False, "code": "SN_REGISTER_ERROR", "error": str(exc)}, 400)


def main():
    init_sn_ledger()
    sync = NgBroadcastSync(DB_PATH, MES_URL)
    NgSyncHandler.sync = sync
    sync.start()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), NgSyncHandler)
    print(f"station-ng-sync listening on 0.0.0.0:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()

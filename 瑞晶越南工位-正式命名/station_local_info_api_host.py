# -*- coding: utf-8 -*-
"""Read-only MES gateway for every station SQLite database on one line.

Each station gets one deterministic port.  The gateway never accepts POST,
PUT, PATCH or DELETE and never executes SQL supplied by a caller.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
LINE_CONFIG = {
    "MANUAL_LINE": {"root": ROOT / "004-手动线", "base": 12000, "line": "L004"},
    "AUTO_LINE": {"root": ROOT / "002-自动线", "base": 12100, "line": "L002"},
}
TABLES = {
    "scans": ("station_scans", "observed_at"),
    "ng": ("station_ng", "observed_at"),
    "test-results": ("test_results", "created_at"),
    "outbox": ("mes_outbox", "created_at"),
    "agent-messages": ("agent_messages", "created_at"),
    "reports": ("station_reports", "created_at"),
    "resources": ("local_resource_reads", "read_at"),
}


def load_stations(line_root: Path):
    config = json.loads((line_root / "stations.json").read_text(encoding="utf-8-sig"))
    return {str(item["stationCode"]): item for item in config.get("stations", [])}


def station_dir(line_root: Path, station_code: str) -> Path:
    stations = load_stations(line_root)
    item = stations.get(station_code)
    if item is None:
        raise KeyError(station_code)
    prefix = f"({int(item['sequence']):02d})"
    matches = sorted(path for path in line_root.iterdir() if path.is_dir() and path.name.startswith(prefix))
    if not matches:
        raise FileNotFoundError(f"station folder {prefix}")
    return matches[0]


def db_files(folder: Path):
    return sorted({*folder.glob("*.sqlite"), *folder.glob("*.db"), *folder.glob("data/*.sqlite"), *folder.glob("data/*.db")})


def safe_rows(folder: Path, table: str, order_column: str, limit: int):
    rows = []
    for db_path in db_files(folder):
        try:
            with sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=2) as db:
                db.row_factory = sqlite3.Row
                exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
                if not exists:
                    continue
                columns = [str(row[1]) for row in db.execute(f'PRAGMA table_info("{table}")')]
                order = order_column if order_column in columns else (columns[0] if columns else "")
                query = f'SELECT * FROM "{table}"' + (f' ORDER BY "{order}" DESC' if order else "") + " LIMIT ?"
                for row in db.execute(query, (limit,)):
                    value = dict(row)
                    value["_database"] = str(db_path.name)
                    rows.append(value)
        except (OSError, sqlite3.Error):
            continue
    return rows[:limit]


def station_payload(line_domain: str, line_root: Path, station_code: str):
    folder = station_dir(line_root, station_code)
    cfg = load_stations(line_root)[station_code]
    return folder, cfg


class Handler(BaseHTTPRequestHandler):
    server_version = "RJ-Station-Local-Info/1.0"

    def do_POST(self):
        self.send_error(405, "read-only API")

    do_PUT = do_POST
    do_PATCH = do_POST
    do_DELETE = do_POST

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            route = parsed.path.rstrip("/") or "/health"
            query = parse_qs(parsed.query)
            limit = min(max(int(query.get("limit", ["200"])[0]), 1), 1000)
            folder, cfg = station_payload(self.server.line_domain, self.server.line_root, self.server.station_code)
            if route == "/health":
                body = {"ok": True, "readOnly": True, "stationCode": self.server.station_code,
                        "lineDomain": self.server.line_domain, "lineCode": self.server.line_code,
                        "port": self.server.server_port, "sqliteFiles": [p.name for p in db_files(folder)],
                        "stationSequence": cfg.get("sequence"), "timestamp": int(time.time() * 1000)}
            elif route == "/api/station/local-info":
                body = {"ok": True, "readOnly": True, "station": {**cfg, "stationCode": self.server.station_code},
                        "lineDomain": self.server.line_domain, "lineCode": self.server.line_code,
                        "port": self.server.server_port, "sqliteFiles": [str(p) for p in db_files(folder)]}
            elif route in ("/api/station/scans", "/api/station/ng", "/api/station/test-results", "/api/station/resources", "/api/station/outbox", "/api/station/agent-messages", "/api/station/reports"):
                key = route.rsplit("/", 1)[-1]
                table, order = TABLES[key]
                body = {"ok": True, "readOnly": True, "stationCode": self.server.station_code,
                        "lineDomain": self.server.line_domain, "items": safe_rows(folder, table, order, limit)}
            else:
                self.send_error(404, "unknown endpoint")
                return
            raw = json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(raw)
        except (KeyError, FileNotFoundError, ValueError) as exc:
            self.send_error(404, str(exc))
        except Exception as exc:
            self.send_error(500, str(exc))

    def log_message(self, fmt, *args):
        print(f"[{self.server.station_code}:{self.server.server_port}] {fmt % args}", flush=True)


def start_one(line_domain: str, line_root: Path, line_code: str, station_code: str, sequence: int):
    server = ThreadingHTTPServer(("0.0.0.0", LINE_CONFIG[line_domain]["base"] + int(sequence)), Handler)
    server.line_domain, server.line_root, server.line_code, server.station_code = line_domain, line_root, line_code, station_code
    print(f"[station-api] {station_code} -> http://0.0.0.0:{server.server_port} (GET-only)", flush=True)
    server.serve_forever(poll_interval=0.5)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--line-domain", choices=sorted(LINE_CONFIG), required=True)
    args = parser.parse_args()
    conf = LINE_CONFIG[args.line_domain]
    stations = load_stations(conf["root"])
    for code, item in stations.items():
        threading.Thread(target=start_one, args=(args.line_domain, conf["root"], conf["line"], code, item["sequence"]), daemon=True).start()
    print(f"[station-api] {args.line_domain}: {len(stations)} read-only SQLite endpoints ready", flush=True)
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
